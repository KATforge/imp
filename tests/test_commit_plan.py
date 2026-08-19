import pytest

from imp_git import ai, commit_plan, git, state
from tests.conftest import commit_count, git_run

ACTOR = "actor:human:anders"


def _lines () -> str:
   return "".join (f"line {number}\n" for number in range (1, 16))


def _prepare (repo):
   (repo / "file.txt").write_text (_lines ())
   git_run (repo, "add", "file.txt")
   git_run (repo, "commit", "-m", "test: add fixture lines")
   (repo / "file.txt").write_text (
      _lines ().replace ("line 2\n", "line two\n").replace ("line 13\n", "line thirteen\n")
   )


class TestPlans:

   def test_root_commit (self, unborn_repo, monkeypatch):
      (unborn_repo / "file.txt").write_text ("first\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add first value")

      result = commit_plan.apply (commit_plan.create (actor_id=ACTOR), ACTOR)

      assert len (result ["commits"]) == 1
      assert git.capture ("show", "HEAD:file.txt").strip () == "first"

   def test_multiple_changes_make_one_commit_off_ref (self, repo, monkeypatch):
      (repo / "first.txt").write_text ("first\n")
      (repo / "second.txt").write_text ("second\n")
      before = git.rev_parse ("HEAD")
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add values")

      plan = commit_plan.create (actor_id=ACTOR)

      assert git.rev_parse ("HEAD") == before
      result = commit_plan.apply (plan, ACTOR)
      assert len (result ["commits"]) == 1
      assert git.is_clean ()

   def test_staged_scope_preserves_unstaged_changes (self, repo, monkeypatch):
      _prepare (repo)
      staged = _lines ().replace ("line 2\n", "line two\n")
      (repo / "file.txt").write_text (staged)
      git_run (repo, "add", "file.txt")
      (repo / "file.txt").write_text (staged.replace ("line 13\n", "line thirteen\n"))
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update first value")

      commit_plan.apply (commit_plan.create (actor_id=ACTOR), ACTOR)

      assert git.capture ("show", "HEAD:file.txt").replace ("\r\n", "\n") == staged
      assert "line thirteen" in (repo / "file.txt").read_text ()

   def test_stale_plan_does_not_move_head (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("planned\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")
      plan = commit_plan.create (actor_id=ACTOR)
      before = git.rev_parse ("HEAD")
      (repo / "file.txt").write_text ("changed later\n")

      with pytest.raises (state.StateError, match="stale"):
         commit_plan.apply (plan, ACTOR)

      assert git.rev_parse ("HEAD") == before

   def test_apply_revalidates_messages (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("planned\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")
      plan = commit_plan.create (actor_id=ACTOR)
      plan ["payload"] ["message"] = "invalid"

      with pytest.raises (state.StateError, match="invalid message"):
         commit_plan.apply (plan, ACTOR)

      assert commit_count (repo) == 1

   def test_build_failure_changes_nothing (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")
      plan = commit_plan.create (actor_id=ACTOR)
      before_head = git.rev_parse ("HEAD")
      before_status = git.capture ("status", "--porcelain=v1")

      def fail (*args):
         raise RuntimeError ("failed")

      monkeypatch.setattr (git, "commit_tree", fail)

      with pytest.raises (RuntimeError, match="failed"):
         commit_plan.apply (plan, ACTOR)

      assert git.rev_parse ("HEAD") == before_head
      assert git.capture ("status", "--porcelain=v1") == before_status

   def test_stale_intent_to_add_is_ignored (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("updated\n")
      (repo / "phantom.txt").write_text ("temp\n")
      git_run (repo, "add", "-N", "phantom.txt")
      (repo / "phantom.txt").unlink ()
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update local value")

      commit_plan.apply (commit_plan.create (actor_id=ACTOR), ACTOR)

      assert git.capture ("show", "HEAD:file.txt") == "updated\n"

   def test_possible_secret_warns (self, repo, monkeypatch):
      (repo / ".env").write_text ("TOKEN=secret\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "chore: update env defaults")

      plan = commit_plan.create (actor_id=ACTOR)

      assert any (warning.startswith ("Possible secret file") for warning in plan ["warnings"])
