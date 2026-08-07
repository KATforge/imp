import sys
from pathlib import Path

import pytest

from imp_git import console, features, git, identity, integration, plans, runtime, source_release, state
from imp_git import repo as repo_mod
from imp_git.commands import commit as commit_cmd
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


class TestDone:

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

   def test_omitted_plan_uses_picker_even_with_one_candidate (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      plan = integration.plan_done (feature, actor_id=ACTOR, keep=True)
      selected = []
      monkeypatch.setattr (runtime, "options", runtime.Options ())
      monkeypatch.setattr (
         console,
         "choose",
         lambda title, values: selected.append ((title, values)) or values [0],
      )

      value = plans.resolve ("done")

      assert value ["plan_id"] == plan ["plan_id"]
      assert selected [0] [0] == "Select imp done plan"
      assert len (selected [0] [1]) == 1

   def test_omitted_plan_fails_closed_without_input (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      integration.plan_done (feature, actor_id=ACTOR, keep=True)
      monkeypatch.setattr (runtime, "options", runtime.Options (no_input=True))

      with pytest.raises (state.StateError, match="explicit imp done plan ID"):
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

   def test_required_review_is_exact_and_human_only (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      original = repo_mod.get
      monkeypatch.setattr (
         integration.repo,
         "get",
         lambda key, default=None: True if key == "review:required" else original (key, default),
      )
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
      assert reviewed ["state"] == "ready"
      assert integration.review_current (reviewed)
      assert integration.reusable_plan (feature) ["plan_id"] == plan ["plan_id"]

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

   def test_human_review_prompts_to_mark_the_exact_candidate (self, repo, tmp_path, monkeypatch):
      feature = _feature (repo, tmp_path)
      prompts = []
      monkeypatch.setattr (console, "interactive", lambda: True)
      monkeypatch.setattr (console, "confirm", lambda message: prompts.append (message) or True)

      value = review_cmd.review (feature ["feature_id"], no_ai=True, actor_id=ACTOR)

      assert prompts == [ "Mark this exact candidate reviewed?" ]
      assert value ["receipt"] ["candidate_oid"] == value ["candidate_oid"]

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

   def test_dirty_source_reports_exact_next_steps (self, repo):
      (repo / "file.txt").write_text ("changed\n")

      with pytest.raises (state.StateError) as error:
         source_release.plan_ship (level="patch")

      assert "Uncommitted changes cannot be shipped" in str (error.value)
      assert "imp commit --all --plan" in str (error.value)
      assert "imp ship --plan" in str (error.value)

   def test_include_dirty_runs_separate_commit_flow_before_ship_plan (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      commits = []
      plan = { "payload": {}, "plan_id": "plan:ship:demo:1", "state": "ready" }
      monkeypatch.setattr (runtime, "options", runtime.Options ())
      monkeypatch.setattr (commit_cmd, "commit", lambda **options: commits.append (options ["all"]))
      monkeypatch.setattr (source_release, "plan_ship", lambda **_options: plan)
      monkeypatch.setattr (ship_cmd, "_show", lambda _plan: None)

      result = ship_cmd.ship (include_dirty=True, plan_only=True)

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
