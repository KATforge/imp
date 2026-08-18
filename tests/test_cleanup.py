import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from imp_git import cleanup, features, git, identity, state
from imp_git.main import app
from tests.conftest import commit_file, git_run

runner = CliRunner ()
ACTOR = identity.resource ("actor", "human", "anders")


def _start (name: str) -> dict:
   return features.apply_start (features.plan_start (name, actor_id=ACTOR))


def _expire (feature: dict):
   path = features._claim_path (str (feature ["feature_id"]))
   claim = state.read (path, "imp.claim.v1")
   claim ["expires_at"] = "2000-01-01T00:00:00Z"
   state.atomic_write (path, claim)


def _recovery (name: str):
   state.atomic_write (state.root () / "recovery" / f"recovery--done--{name}--1.json", {
      "schema": "imp.recovery.v1",
      "recovery_id": f"recovery:done:{name}:1",
      "command": "imp done",
      "label": name,
      "candidate_oid": "0" * 40,
      "target_ref": "master",
      "completed": [],
      "error": "interrupted",
      "next": f"imp done {name}",
      "created_at": "2026-08-17T00:00:00Z",
   })


class TestCleanup:

   def test_settles_empty_feature_and_its_recovery (self, repo_with_origin):
      feature = _start ("empty")
      _expire (feature)
      _recovery ("empty")

      plan = cleanup.plan_cleanup ()
      data = cleanup.apply_cleanup (plan, ACTOR)

      assert { item ["action"] for item in data ["applied"] } == { "settle_feature", "clear_recovery" }
      assert data ["clean"] is True
      assert features.find ("empty") is None
      assert not Path (feature ["path"]).exists ()
      assert not git.ref_exists (str (feature ["branch"]))
      assert state.recoveries () == []

   def test_releases_expired_claim_but_preserves_unique_commits (self, repo_with_origin):
      feature = _start ("ready")
      commit_file (Path (feature ["path"]), "ready.txt", "ready\n", "feat: ready")
      _expire (feature)

      data = cleanup.apply_cleanup (cleanup.plan_cleanup (), ACTOR)

      retained = features.find ("ready")
      assert data ["clean"] is False
      assert retained ["claim"] is None
      assert retained ["worktree_state"] == "live"
      assert data ["remaining"] [0] ["next"] == "imp done ready"

   def test_preserves_dirty_worktree_with_review_next (self, repo_with_origin):
      feature = _start ("dirty")
      _expire (feature)
      Path (feature ["path"], "dirty.txt").write_text ("dirty\n")

      data = cleanup.apply_cleanup (cleanup.plan_cleanup (), ACTOR)

      assert Path (feature ["path"], "dirty.txt").read_text () == "dirty\n"
      assert data ["remaining"] [0] ["reason"] == "uncommitted changes"
      assert data ["remaining"] [0] ["next"] == "imp review dirty"

   def test_restores_missing_worktree_for_unmerged_branch (self, repo_with_origin):
      feature = _start ("missing")
      commit_file (Path (feature ["path"]), "missing.txt", "missing\n", "feat: missing")
      _expire (feature)
      git.worktree_remove (str (feature ["path"]))

      data = cleanup.apply_cleanup (cleanup.plan_cleanup (), ACTOR)

      assert Path (feature ["path"]).exists ()
      assert { item ["action"] for item in data ["applied"] } == {
         "release_expired_claim", "restore_feature",
      }
      assert data ["remaining"] [0] ["next"] == "imp done missing"

   def test_removes_merged_orphan (self, repo_with_origin, tmp_path):
      path = tmp_path / "orphan"
      git_run (repo_with_origin, "worktree", "add", "-b", "feature/orphan", str (path), "master")
      git_run (repo_with_origin, "config", "branch.feature/orphan.cleanup", "remove")

      data = cleanup.apply_cleanup (cleanup.plan_cleanup (), ACTOR)

      assert data ["clean"] is True
      assert not path.exists ()
      assert not git.ref_exists ("feature/orphan")
      assert not git.capture ("config", "--get", "branch.feature/orphan.cleanup").strip ()

   def test_discards_unique_branch_after_feature_was_removed (self, repo_with_origin):
      feature = _start ("abandoned")
      commit_file (Path (feature ["path"]), "abandoned.txt", "abandoned\n", "feat: abandoned")
      plan = features.plan_remove (feature, actor_id=ACTOR)
      features.apply_remove (plan, ACTOR)

      data = cleanup.apply_cleanup (cleanup.plan_cleanup (), ACTOR)

      assert data ["clean"] is True
      assert features.find ("abandoned") is None
      assert not git.ref_exists (str (feature ["branch"]))

   def test_names_integration_conflicts (self, repo_with_origin):
      feature = _start ("conflict")
      Path (feature ["path"], "file.txt").write_text ("feature\n")
      git_run (feature ["path"], "add", "file.txt")
      git_run (feature ["path"], "commit", "-m", "feat: conflict")
      git_run (repo_with_origin, "checkout", "master")
      commit_file (repo_with_origin, "file.txt", "target\n", "fix: conflict")
      _expire (feature)

      plan = cleanup.plan_cleanup ()
      remaining = plan ["payload"] ["remaining"] [0]

      assert remaining ["reason"] == "integration conflicts: file.txt"
      assert remaining ["next"] == "imp done conflict --resolve ask"

   def test_rejects_stale_plan (self, repo_with_origin):
      feature = _start ("moving")
      _expire (feature)
      plan = cleanup.plan_cleanup ()
      commit_file (Path (feature ["path"]), "moving.txt", "moving\n", "feat: moving")

      with pytest.raises (state.StateError, match="stale"):
         cleanup.apply_cleanup (plan, ACTOR)

      assert Path (feature ["path"]).exists ()
      assert git.ref_exists (str (feature ["branch"]))

   def test_json_reports_preserved_claim_without_prompt (self, repo_with_origin):
      _start ("claimed")

      result = runner.invoke (app, [ "--json", "cleanup" ])
      value = json.loads (result.stdout)

      assert result.exit_code == 0
      assert value ["schema"] == "imp.cleanup.v1"
      assert value ["data"] ["clean"] is False
      assert value ["data"] ["remaining"] [0] ["reason"].startswith ("claimed by")
