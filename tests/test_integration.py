import sys
from pathlib import Path

import pytest
import typer

from imp_git import ai, console, features, git, identity, integration, plans, runtime, source_release, state
from imp_git.commands import commit as commit_cmd
from imp_git.commands import done as done_cmd
from imp_git.commands import review as review_cmd
from imp_git.commands import ship as ship_cmd
from tests.conftest import commit_file, git_run

ACTOR = identity.resource ("actor", "human", "anders")


def _feature (repo: Path, tmp_path: Path, name: str = "checkout") -> dict:
   path = repo.parent / f"{repo.name}-{name}-worktree"
   plan = features.plan_start (name, actor_id=ACTOR, path=str (path))
   feature = features.apply_start (plan)
   commit_file (Path (feature ["path"]), f"{name}.txt", f"{name}\n", f"feat: add {name}")
   return features.find (feature ["feature_id"])


class TestIntegration:

   def test_omitted_feature_uses_picker_even_with_one_candidate (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      selected = []
      monkeypatch.setattr (
         console,
         "choose",
         lambda title, values: selected.append ((title, values)) or values [0],
      )

      value = features.resolve (
         "",
         states={ "active", "awaiting-merge" },
         title="Select feature to complete",
      )

      assert value ["feature_id"] == feature ["feature_id"]
      assert selected == [
         (
            "Select feature to complete",
            [ "checkout · active · feature/checkout" ],
         )
      ]

   def test_omitted_feature_fails_closed_without_input (self, repo, tmp_path, monkeypatch):
      _feature (repo, tmp_path)
      monkeypatch.setattr (runtime, "options", runtime.Options (no_input=True))

      with pytest.raises (state.StateError, match="explicit feature"):
         features.resolve ("", title="Select feature to complete")

   def test_omitted_plan_uses_the_newest_ready_plan (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      oldest = integration.plan_done (feature, actor_id=ACTOR, keep=True)
      monkeypatch.setattr (state, "now", lambda: "2999-01-01T00:00:00Z")
      newest = integration.plan_done (feature, actor_id=ACTOR, keep=True)
      assert newest ["plan_id"] != oldest ["plan_id"]
      monkeypatch.setattr (runtime, "options", runtime.Options ())
      monkeypatch.setattr (console, "choose", lambda title, values: pytest.fail ("Plans must not prompt"))

      assert plans.resolve ("done") ["plan_id"] == newest ["plan_id"]

   def test_omitted_plan_resolves_without_input (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      plan = integration.plan_done (feature, actor_id=ACTOR, keep=True)
      monkeypatch.setattr (runtime, "options", runtime.Options (no_input=True))

      assert plans.resolve ("done") ["plan_id"] == plan ["plan_id"]

   def test_omitted_plan_fails_closed_without_a_ready_plan (self, repo, tmp_path, monkeypatch):
      _feature (repo, tmp_path)
      monkeypatch.setattr (runtime, "options", runtime.Options (no_input=True))

      with pytest.raises (state.StateError, match="No ready imp done plan"):
         plans.resolve ("done")

   def test_failed_checks_leave_target_and_feature_unchanged (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      target_before = git.rev_parse ("main")
      feature_before = git.rev_parse (str (feature ["branch"]))
      monkeypatch.setattr (
         integration,
         "_checks",
         lambda: [ { "name": "tests", "run": [ sys.executable, "-c", "raise SystemExit(1)" ] } ],
      )

      plan = integration.plan_done (feature, actor_id=ACTOR)

      assert plan ["state"] == "blocked"
      assert plan ["blockers"] == [ "Check failed: tests" ]
      assert git.rev_parse ("main") == target_before
      assert git.rev_parse (str (feature ["branch"])) == feature_before


   def test_plan_is_read_only_and_apply_integrates_exact_candidate (self, repo, tmp_path):
      feature = _feature (repo, tmp_path)
      before = git.rev_parse ("main")

      plan = integration.plan_done (feature, actor_id=ACTOR)

      assert plan ["state"] == "ready"
      assert git.rev_parse ("main") == before
      assert plan ["payload"] ["candidate_tree_oid"] == git.tree (plan ["payload"] ["candidate_oid"])

      receipt = integration.apply_done (plan, ACTOR)

      assert receipt ["candidate_oid"] == git.rev_parse ("main")
      assert git.capture ("show", "main:checkout.txt").strip () == "checkout"
      assert features.find (feature ["feature_id"]) ["state"] == "completed"
      assert not Path (feature ["path"]).exists ()

   def test_apply_refuses_a_moved_target (self, repo, tmp_path):
      feature = _feature (repo, tmp_path)
      plan = integration.plan_done (feature, actor_id=ACTOR, keep=True)
      commit_file (repo, "other.txt", "other\n", "chore: move target")

      with pytest.raises (state.StateError, match="target moved"):
         integration.apply_done (plan, ACTOR)

      assert features.find (feature ["feature_id"]) ["state"] == "active"

   def test_push_failure_can_resume_the_same_plan (self, repo_with_origin, tmp_path, monkeypatch):
      feature = _feature (repo_with_origin, tmp_path)
      plan = integration.plan_done (feature, actor_id=ACTOR, push=True)
      candidate = plan ["payload"] ["candidate_oid"]
      original = git.push
      attempts = []

      def push (*args, **kwargs):
         attempts.append (True)
         if len (attempts) == 1:
            raise state.StateError ("network unavailable")
         return original (*args, **kwargs)

      monkeypatch.setattr (integration.git, "push", push)

      with pytest.raises (state.StateError, match="network unavailable"):
         integration.apply_done (plan, ACTOR)

      receipt = integration.apply_done (plan, ACTOR)

      assert receipt ["candidate_oid"] == candidate
      assert git.rev_parse (f"origin/{plan ['payload']['target_ref']}") == candidate
      assert attempts == [ True, True ]
      assert not list ((state.root () / "recovery").glob ("*.json"))

   def test_agent_work_requires_exact_human_review (self, repo, tmp_path):
      feature = _feature (repo, tmp_path)
      features.release (feature, ACTOR)
      features.claim (feature, identity.resource ("actor", "codex", "session-1"))
      feature = features.find (feature ["feature_id"])
      plan = integration.plan_done (feature, actor_id=ACTOR, keep=True)

      assert plan ["state"] == "blocked"
      with pytest.raises (state.StateError, match="Only a human"):
         integration.mark_reviewed (
            plan,
            identity.resource ("actor", "codex", "session-1"),
            files=[ "checkout.txt" ],
            findings={ "blocker": 0, "warning": 0, "note": 0 },
         )

      receipt = integration.mark_reviewed (
         plan,
         ACTOR,
         files=[ "checkout.txt" ],
         findings={ "blocker": 0, "warning": 0, "note": 0 },
      )
      reviewed = plans.load (plan ["plan_id"])

      assert receipt ["candidate_oid"] == plan ["payload"] ["candidate_oid"]
      assert receipt ["decision"] == "reviewed"
      assert reviewed ["state"] == "ready"
      assert reviewed ["reviewed_at"] == receipt ["reviewed_at"]
      assert integration.approval_current (reviewed)
      assert integration.reusable_plan (feature) ["plan_id"] == plan ["plan_id"]

   def test_human_can_explicitly_approve_without_review (self, repo, tmp_path):
      feature = _feature (repo, tmp_path)
      features.release (feature, ACTOR)
      features.claim (feature, identity.resource ("actor", "codex", "session-1"))

      plan = done_cmd.done (
         feature ["feature_id"],
         approve=True,
         plan_only=True,
         actor_id=ACTOR,
      )
      receipt = integration.approval_receipt (feature ["feature_id"])

      assert plan ["state"] == "ready"
      assert receipt ["decision"] == "approved_without_review"
      assert "reviewed_at" not in receipt
      assert integration.approval_current (plan)

   def test_agent_cannot_use_explicit_approval_override (self, repo, tmp_path):
      feature = _feature (repo, tmp_path)

      with pytest.raises (typer.Exit):
         done_cmd.done (
            feature ["feature_id"],
            approve=True,
            plan_only=True,
            actor_id=identity.resource ("actor", "codex", "session-1"),
         )

   def test_machine_review_includes_the_complete_diff (self, repo, tmp_path):
      feature = _feature (repo, tmp_path)

      value = review_cmd.review (
         feature ["feature_id"],
         no_ai=True,
         json_output=True,
         actor_id=ACTOR,
      )

      assert "checkout.txt" in value ["diff"]
      assert "+checkout" in value ["diff"]
      assert value ["files"] == [ "checkout.txt" ]

   def test_review_uses_the_current_managed_worktree (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      monkeypatch.chdir (feature ["path"])
      monkeypatch.setattr (
         console,
         "choose",
         lambda *_args: pytest.fail ("current worktree should not open the feature picker"),
      )

      value = review_cmd.review (no_ai=True, json_output=True, actor_id=ACTOR)

      assert value ["feature_id"] == feature ["feature_id"]

   def test_dirty_review_commits_after_exact_approval (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      path = Path (feature ["path"])
      (path / "dirty.txt").write_text ("dirty\n")
      monkeypatch.setattr (ai, "fast", lambda _prompt: "fix: commit review candidate")
      monkeypatch.setattr (console, "confirm", lambda message: message.startswith ("Create "))

      value = review_cmd.review (feature ["feature_id"], no_ai=True, actor_id=ACTOR)

      assert git.clean_at (str (path))
      assert git.capture ("-C", str (path), "log", "-1", "--format=%s").strip () == (
         "fix: commit review candidate"
      )
      assert value ["receipt"] is None

   def test_dirty_review_never_commits_without_exact_approval (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      path = Path (feature ["path"])
      before = git.capture ("-C", str (path), "rev-parse", "HEAD").strip ()
      (path / "dirty.txt").write_text ("dirty\n")
      monkeypatch.setattr (ai, "fast", lambda _prompt: "fix: commit review candidate")
      monkeypatch.setattr (console, "confirm", lambda _message: False)

      with pytest.raises (typer.Exit):
         review_cmd.review (feature ["feature_id"], no_ai=True, actor_id=ACTOR)

      assert git.capture ("-C", str (path), "rev-parse", "HEAD").strip () == before
      assert not git.clean_at (str (path))

   def test_human_review_prompts_to_mark_the_exact_candidate (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      prompts = []
      monkeypatch.setattr (console, "interactive", lambda: True)
      monkeypatch.setattr (console, "confirm", lambda message: prompts.append (message) or True)

      value = review_cmd.review (feature ["feature_id"], no_ai=True, actor_id=ACTOR)

      assert prompts == [ "Mark this exact candidate reviewed?" ]
      assert value ["receipt"] ["candidate_oid"] == value ["candidate_oid"]

   def test_human_review_can_apply_smart_fixes (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      responses = iter ([
         "The checkout value should be clearer.",
         """diff --git a/checkout.txt b/checkout.txt
--- a/checkout.txt
+++ b/checkout.txt
@@ -1 +1 @@
-checkout
+fixed checkout
""",
      ])
      monkeypatch.setattr (ai, "smart", lambda prompt, spin=True: next (responses))
      monkeypatch.setattr (console, "interactive", lambda: True)
      monkeypatch.setattr (console, "choose", lambda _title, values: values [0])

      value = review_cmd.review (feature ["feature_id"], actor_id=ACTOR)

      assert value ["fix"] == { "applied": True, "files": [ "checkout.txt" ] }
      assert value ["receipt"] is None
      assert value ["mark_available"] is False
      assert (Path (feature ["path"]) / "checkout.txt").read_text () == "fixed checkout\n"

   def test_smart_fix_cannot_escape_reviewed_files (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      responses = iter ([
         "Change an unrelated file.",
         """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
-hello
+changed
""",
      ])
      monkeypatch.setattr (ai, "smart", lambda prompt, spin=True: next (responses))

      with pytest.raises (typer.Exit):
         review_cmd.review (feature ["feature_id"], fix=True, actor_id=ACTOR)

      assert (Path (feature ["path"]) / "file.txt").read_text () == "hello\n"
      assert git.clean_at (str (feature ["path"]))

   def test_pull_request_keeps_worktree_until_merge_is_observed (
      self,
      repo_with_origin,
      tmp_path,
      monkeypatch,
   ):
      feature = _feature (repo_with_origin, tmp_path, "profile")
      monkeypatch.setattr (integration.gh, "pr_view", lambda _head: {})
      monkeypatch.setattr (
         integration.gh,
         "pr_create",
         lambda _title, _body, _base, _head: "https://github.com/katforge/demo/pull/1",
      )
      plan = integration.plan_done (feature, actor_id=ACTOR, pr=True)

      receipt = integration.apply_done (plan, ACTOR)

      retained = features.find (feature ["feature_id"])
      assert receipt ["mode"] == "pr"
      assert retained ["state"] == "awaiting-merge"
      assert Path (feature ["path"]).is_dir ()

   def test_pull_request_rejects_attribution_before_push (self, repo_with_origin, tmp_path, monkeypatch):
      feature = _feature (repo_with_origin, tmp_path, "profile")
      commit_file (
         Path (feature ["path"]),
         "extra.txt",
         "extra\n",
         "Generated with Claude Code",
      )
      plan = integration.plan_done (feature, actor_id=ACTOR, pr=True)
      pushed = []
      monkeypatch.setattr (integration.git, "push", lambda *args, **kwargs: pushed.append (True))

      with pytest.raises (state.StateError, match="Pull request text"):
         integration.apply_done (plan, ACTOR)

      assert pushed == []
      assert features.find (feature ["feature_id"]) ["state"] == "active"


class TestSourceRelease:

   def test_prerelease_is_exact_and_increments_candidates (self, repo, monkeypatch):
      git.tag ("v1.2.3")
      releases = []
      monkeypatch.setattr (source_release.gh, "available", lambda: True)
      monkeypatch.setattr (source_release.git, "remote_exists", lambda: False)
      monkeypatch.setattr (source_release, "_repository_url", lambda tag: f"https://example.test/{tag}")

      first = source_release.plan_ship (level="patch", prerelease=True)

      assert first ["payload_schema"] == "imp.ship-plan.v2"
      assert first ["payload"] ["version"] == "1.2.4-rc.1"
      assert first ["payload"] ["tag"] == "v1.2.4-rc.1"
      assert first ["payload"] ["prerelease"] is True

      first ["payload"] ["github_release"] = True
      monkeypatch.setattr (source_release.gh, "release_view", lambda _tag: {})
      monkeypatch.setattr (
         source_release.gh,
         "release_create",
         lambda version, notes, prerelease=False: releases.append ((version, prerelease)) or True,
      )
      receipt = source_release.apply_ship (first)

      assert receipt ["prerelease"] is True
      assert releases == [ ("1.2.4-rc.1", True) ]

      second = source_release.plan_ship (level="patch", prerelease=True)

      assert second ["payload"] ["version"] == "1.2.4-rc.2"

   def test_stable_release_rejects_prerelease_version (self, repo):
      with pytest.raises (state.StateError, match=r"must be X\.Y\.Z"):
         source_release.plan_ship (set_version="1.2.3-rc.1")

   def test_github_release_failure_is_not_reported_as_success (self, repo, monkeypatch):
      plan = source_release.plan_ship (level="patch")
      plan ["payload"] ["github_release"] = True
      monkeypatch.setattr (source_release.gh, "release_view", lambda _tag: {})
      monkeypatch.setattr (source_release.gh, "release_create", lambda *_args, **_kwargs: False)

      with pytest.raises (state.StateError, match="GitHub release creation failed"):
         source_release.apply_ship (plan)

   def test_github_release_failure_can_resume_the_same_plan (self, repo, monkeypatch):
      plan = source_release.plan_ship (level="patch")
      plan ["payload"] ["github_release"] = True
      attempts = []

      def create (*_args, **_kwargs):
         attempts.append (True)
         return len (attempts) > 1

      monkeypatch.setattr (source_release.gh, "release_view", lambda _tag: {})
      monkeypatch.setattr (source_release.gh, "release_create", create)

      with pytest.raises (state.StateError, match="GitHub release creation failed"):
         source_release.apply_ship (plan)

      receipt = source_release.apply_ship (plan)

      assert receipt ["tag"] == "v0.0.1"
      assert attempts == [ True, True ]
      assert not list ((state.root () / "recovery").glob ("*.json"))

   def test_dirty_source_reports_exact_next_steps (self, repo):
      (repo / "file.txt").write_text ("changed\n")

      with pytest.raises (state.StateError) as error:
         source_release.plan_ship (level="patch")

      assert "Uncommitted changes cannot be shipped" in str (error.value)
      assert "imp commit --all --plan" in str (error.value)
      assert "imp ship --plan" in str (error.value)

   def test_commit_runs_separate_commit_flow_before_ship_plan (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      commits = []
      plan = { "payload": {}, "plan_id": "plan:ship:demo:1", "state": "ready" }
      monkeypatch.setattr (runtime, "options", runtime.Options ())
      monkeypatch.setattr (commit_cmd, "commit", lambda **options: commits.append (options ["all"]))
      monkeypatch.setattr (source_release, "plan_ship", lambda **_options: plan)
      monkeypatch.setattr (ship_cmd, "_show", lambda _plan: None)

      result = ship_cmd.ship (commit=True, plan_only=True)

      assert result == plan
      assert commits == [ True ]

   def test_apply_revalidates_release_notes (self, repo):
      plan = source_release.plan_ship (level="patch")
      before = git.rev_parse ("main")
      plan ["payload"] ["changelog"] = "Generated with Claude Code"

      with pytest.raises (state.StateError, match="Release notes"):
         source_release.apply_ship (plan)

      assert git.rev_parse ("main") == before
      assert not git.tag_exists ("v0.0.1")

   def test_plan_bumps_manifest_and_changelog_before_exact_apply (self, repo):
      (repo / "pyproject.toml").write_text ('[project]\nname = "demo"\nversion = "1.2.3"\n')
      commit_file (repo, "CHANGELOG.md", "# Changelog\n", "chore: add release files")
      git_run (repo, "add", "pyproject.toml")
      git_run (repo, "commit", "-m", "feat: add package metadata")
      before = git.rev_parse ("main")

      plan = source_release.plan_ship (level="patch")

      assert plan ["payload"] ["version"] == "0.0.1"
      assert plan ["payload"] ["manifest_versions"] == { "pyproject.toml": "0.0.1" }
      assert "- Added package metadata" in plan ["payload"] ["changelog"]
      assert git.rev_parse ("main") == before

      receipt = source_release.apply_ship (plan)

      assert receipt ["tag"] == "v0.0.1"
      assert git.rev_parse ("v0.0.1") == git.rev_parse ("main")
      assert 'version = "0.0.1"' in (repo / "pyproject.toml").read_text ()
      assert "- Added package metadata" in (repo / "CHANGELOG.md").read_text ()
