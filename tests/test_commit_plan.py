import json

import pytest

from imp_git import ai, commit_plan, git, identity, plans, state
from tests.conftest import commit_count, git_run


def _actor () -> str:
   return identity.resource ("actor", "human", "anders")


def _lines () -> str:
   return "".join (f"line {number}\n" for number in range (1, 16))


def _prepare_changes (repo):
   (repo / "file.txt").write_text (_lines ())
   git_run (repo, "add", "file.txt")
   git_run (repo, "commit", "-m", "test: add fixture lines")
   changed = _lines ().replace ("line 2\n", "line two\n").replace ("line 13\n", "line thirteen\n")
   (repo / "file.txt").write_text (changed)


class TestPlans:

   def test_plan_and_apply_create_a_root_commit (self, unborn_repo, monkeypatch):
      (unborn_repo / "file.txt").write_text ("first\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add first value")

      plan = commit_plan.create (actor_id=_actor (), all_changes=True, single=True)

      assert plan ["payload"] ["head_oid"] == ""

      result = commit_plan.apply (plan, _actor ())

      assert len (result ["commits"]) == 1
      assert git.capture ("rev-list", "--parents", "-n", "1", "HEAD").split () [1:] == []
      assert git.capture ("show", "HEAD:file.txt").strip () == "first"
      assert git.is_clean ()

   def test_plan_is_read_only_and_apply_splits_one_file_by_change (self, repo, monkeypatch):
      _prepare_changes (repo)
      before = git.rev_parse ("HEAD")
      response = [
         { "changes": [ "file.txt#1" ], "message": "fix: update first value" },
         { "changes": [ "file.txt#2" ], "message": "feat: update second value" },
      ]
      monkeypatch.setattr (ai, "smart", lambda prompt: json.dumps (response))

      plan = commit_plan.create (actor_id=_actor (), all_changes=True)

      assert git.rev_parse ("HEAD") == before
      assert [group ["changes"] for group in plan ["payload"] ["groups"]] == [
         [ "file.txt#1" ],
         [ "file.txt#2" ],
      ]

      result = commit_plan.apply (plan, _actor ())

      assert len (result ["commits"]) == 2
      assert git.capture ("show", "HEAD~1:file.txt").replace ("\r\n", "\n") == _lines ().replace (
         "line 2\n", "line two\n"
      )
      assert git.is_clean ()

   def test_planner_bounds_large_changes_without_dropping_sections (self, repo, monkeypatch):
      (repo / "large-a.txt").write_text ("a" * 200_000)
      (repo / "large-b.txt").write_text ("b" * 200_000)
      prompts = []
      monkeypatch.setattr (ai, "fast", lambda prompt: prompts.append (prompt) or "chore: add large fixtures")

      commit_plan.create (actor_id=_actor (), all_changes=True, single=True)

      assert "large-a.txt#1" in prompts [0]
      assert "large-b.txt#1" in prompts [0]
      assert len (prompts [0]) < ai.MAX_DIFF_CHARS + 5_000

   def test_staged_plan_preserves_unstaged_changes_in_same_file (self, repo, monkeypatch):
      _prepare_changes (repo)
      staged = _lines ().replace ("line 2\n", "line two\n")
      (repo / "file.txt").write_text (staged)
      git_run (repo, "add", "file.txt")
      (repo / "file.txt").write_text (staged.replace ("line 13\n", "line thirteen\n"))
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update first value")

      plan = commit_plan.create (actor_id=_actor (), staged=True)
      commit_plan.apply (plan, _actor ())

      assert git.capture ("show", "HEAD:file.txt").replace ("\r\n", "\n") == staged
      assert "line thirteen" in (repo / "file.txt").read_text ()
      assert git.diff ()
      assert not git.diff (staged=True)

   def test_excluded_staged_path_remains_staged (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("selected\n")
      (repo / "other.txt").write_text ("preserved\n")
      git_run (repo, "add", "file.txt", "other.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update selected value")

      plan = commit_plan.create (actor_id=_actor (), exclude=[ "other.txt" ], staged=True)
      commit_plan.apply (plan, _actor ())

      assert git.staged_files () == [ "other.txt" ]
      assert git.capture ("show", "HEAD:file.txt").strip () == "selected"

   def test_stale_plan_refuses_without_moving_head (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("planned\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")
      plan = commit_plan.create (actor_id=_actor (), all_changes=True)
      before = git.rev_parse ("HEAD")
      (repo / "file.txt").write_text ("changed later\n")

      with pytest.raises (state.StateError, match="stale"):
         commit_plan.apply (plan, _actor ())

      assert git.rev_parse ("HEAD") == before

   def test_apply_revalidates_commit_messages (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("planned\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")
      plan = commit_plan.create (actor_id=_actor (), all_changes=True)
      before = git.rev_parse ("HEAD")
      plan ["payload"] ["groups"] [0] ["message"] = (
         "fix: update value\n\nCo-Authored-By: Bot <bot@example.com>"
      )

      with pytest.raises (state.StateError, match="invalid message"):
         commit_plan.apply (plan, _actor ())

      assert git.rev_parse ("HEAD") == before

   def test_mid_apply_change_keeps_the_plan_stale (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("planned\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")
      plan = commit_plan.create (actor_id=_actor (), all_changes=True)
      values = iter ([ plan ["fingerprint"], "changed", "changed" ])
      monkeypatch.setattr (commit_plan.fingerprint, "repository", lambda: next (values))

      with pytest.raises (state.StateError, match="changed while commits were prepared"):
         commit_plan.apply (plan, _actor ())

      assert plans.load (plan ["plan_id"]) ["state"] == "stale"

   def test_apply_rejects_older_commit_plan_names (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("planned\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")
      plan = commit_plan.create (actor_id=_actor (), all_changes=True)
      plan ["payload_schema"] = "imp.commit-plan.v1"

      with pytest.raises (state.StateError, match="older format"):
         commit_plan.apply (plan, _actor ())

      assert commit_count (repo) == 1

   def test_build_failure_leaves_head_index_and_worktree_unchanged (self, repo, monkeypatch):
      _prepare_changes (repo)
      response = [
         { "changes": [ "file.txt#1" ], "message": "fix: update first value" },
         { "changes": [ "file.txt#2" ], "message": "feat: update second value" },
      ]
      monkeypatch.setattr (ai, "smart", lambda prompt: json.dumps (response))
      plan = commit_plan.create (actor_id=_actor (), all_changes=True)
      before_head = git.rev_parse ("HEAD")
      before_status = git.capture ("status", "--porcelain=v1")
      real_commit_tree = git.commit_tree
      calls = []

      def fail_second (tree, parent, message):
         calls.append (message)
         if len (calls) == 2:
            raise RuntimeError ("injected failure")
         return real_commit_tree (tree, parent, message)

      monkeypatch.setattr (git, "commit_tree", fail_second)

      with pytest.raises (RuntimeError, match="injected failure"):
         commit_plan.apply (plan, _actor ())

      assert git.rev_parse ("HEAD") == before_head
      assert git.capture ("status", "--porcelain=v1") == before_status

   def test_real_index_failure_rolls_back_the_branch_and_index (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("planned\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")
      plan = commit_plan.create (actor_id=_actor (), staged=True)
      before_head = git.rev_parse ("HEAD")
      before_index = git.diff (staged=True)
      monkeypatch.setattr (git, "reset_mixed", lambda ref: (_ for _ in ()).throw (RuntimeError ("index failure")))

      with pytest.raises (RuntimeError, match="index failure"):
         commit_plan.apply (plan, _actor ())

      assert git.rev_parse ("HEAD") == before_head
      assert git.diff (staged=True) == before_index
      assert (repo / "file.txt").read_text () == "planned\n"

   def test_possible_secret_blocks_before_ai (self, repo, monkeypatch):
      (repo / ".env").write_text ("TOKEN=secret\n")
      called = []
      monkeypatch.setattr (ai, "fast", lambda prompt: called.append (prompt))

      plan = commit_plan.create (actor_id=_actor (), all_changes=True)

      assert plan ["state"] == "blocked"
      assert plan ["blockers"]
      assert "TOKEN=secret" not in json.dumps (plan)
      assert called == []

   def test_amend_replaces_only_the_last_unpublished_commit (self, repo, monkeypatch):
      (repo / "second.txt").write_text ("second\n")
      git_run (repo, "add", "second.txt")
      git_run (repo, "commit", "-m", "feat: add second value")
      original_parent = git.rev_parse ("HEAD^")
      original_count = commit_count (repo)
      (repo / "file.txt").write_text ("amended\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: amend local value")

      plan = commit_plan.create (actor_id=_actor (), amend=True, staged=True)
      commit_plan.apply (plan, _actor ())

      assert commit_count (repo) == original_count
      assert git.rev_parse ("HEAD^") == original_parent
      assert git.capture ("log", "-1", "--format=%s").strip () == "fix: amend local value"

   def test_amend_refuses_a_published_head (self, repo_with_origin):
      git_run (repo_with_origin, "checkout", "master")
      (repo_with_origin / "file.txt").write_text ("amended\n")
      git_run (repo_with_origin, "add", "file.txt")

      with pytest.raises (state.StateError, match="published"):
         commit_plan.create (actor_id=_actor (), amend=True, staged=True)
