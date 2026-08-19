import json
import os
from pathlib import Path

import pytest

from imp_git import ai, commit_plan, features, git, identity, state


def _actor (kind: str, name: str) -> str:
   return identity.resource ("actor", kind, name)


def _start (name, actor_id):
   plan = features.plan_start (name, actor_id=actor_id)
   return plan, features.apply_start (plan)


class TestFeatures:

   def test_start_plan_is_read_only_and_uses_fresh_remote_trunk (self, repo_with_origin, tmp_path):
      actor_id = _actor ("codex", "payments")
      path = tmp_path / "payments"

      plan = features.plan_start ("payments", actor_id=actor_id)

      assert not path.exists ()
      assert not git.ref_exists ("feature/payments")
      assert plan ["payload"] ["base:oid"] == git.rev_parse ("origin/master")

      feature = features.apply_start (plan)

      assert feature ["feature_id"] == "feature:payments"
      assert feature ["claim"] ["held_by"] == actor_id
      assert git.rev_parse ("feature/payments") == git.rev_parse ("origin/master")
      assert not (path / "wip.txt").exists ()

   def test_two_agents_commit_in_isolated_worktrees (self, repo_with_origin, tmp_path, monkeypatch):
      first_actor = _actor ("codex", "payments")
      second_actor = _actor ("claude", "profile")
      _first_plan, first = _start ("payments", first_actor)
      _second_plan, second = _start ("profile", second_actor)
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add isolated marker")

      monkeypatch.chdir (first ["path"])
      Path ("payments.txt").write_text ("payments\n")
      first_commit = commit_plan.create (actor_id=first_actor)
      commit_plan.apply (first_commit, first_actor)

      monkeypatch.chdir (second ["path"])
      Path ("profile.txt").write_text ("profile\n")
      second_commit = commit_plan.create (actor_id=second_actor)
      commit_plan.apply (second_commit, second_actor)

      assert git.capture ("show", "feature/payments:payments.txt").strip () == "payments"
      assert not git.succeeds ("cat-file", "-e", "feature/payments:profile.txt")
      assert git.capture ("show", "feature/profile:profile.txt").strip () == "profile"
      assert not git.succeeds ("cat-file", "-e", "feature/profile:payments.txt")

   def test_claim_prevents_a_second_writer (self, repo_with_origin, tmp_path, monkeypatch):
      owner = _actor ("codex", "owner")
      intruder = _actor ("claude", "intruder")
      _plan, feature = _start ("claimed", owner)
      monkeypatch.chdir (feature ["path"])

      with pytest.raises (state.StateError, match="claim held by"):
         features.assert_write_access (intruder)

      features.assert_write_access (owner)

   def test_expired_claim_allows_a_new_writer (self, repo_with_origin, tmp_path):
      owner = _actor ("codex", "owner")
      intruder = _actor ("claude", "intruder")
      _plan, feature = _start ("claimed", owner)
      claim_path = features._claim_path (feature ["feature_id"])
      record = state.read (claim_path, "imp.claim.v1")
      record ["expires_at"] = "2000-01-01T00:00:00Z"
      state.atomic_write (claim_path, record)

      claim = features.claim (feature, intruder)

      assert claim ["held_by"] == intruder
      assert features.find (feature ["feature_id"]) ["claim"] ["held_by"] == intruder

   def test_feature_worktree_does_not_disturb_the_current_branch (self, repo_with_origin, tmp_path):
      original_branch = git.branch ()

      _plan, feature = _start ("payments", _actor ("human", "anders"))

      assert Path (feature ["path"]).is_dir ()
      assert git.branch () == original_branch

   def test_clean_worktree_removal_discards_everything (self, repo_with_origin, tmp_path):
      actor_id = _actor ("human", "anders")
      _start_plan, feature = _start ("temporary", actor_id)

      plan = features.plan_remove (feature, actor_id=actor_id)

      assert Path (feature ["path"]).exists ()
      result = features.apply_remove (plan, actor_id)

      assert result ["feature_id"] == feature ["feature_id"]
      assert not Path (feature ["path"]).exists ()
      assert features.find (feature ["feature_id"]) is None
      assert not git.ref_exists (feature ["branch"])

   def test_completing_from_inside_the_worktree_leaves_a_live_directory (self, repo_with_origin, tmp_path):
      actor_id = _actor ("human", "anders")
      _plan, feature = _start ("stepping", actor_id)
      os.chdir (feature ["path"])

      features.complete (feature)

      assert Path.cwd ().exists ()
      assert not Path (feature ["path"]).exists ()
      assert features.find (feature ["feature_id"]) is None


class TestFeatureMigration:
   """An existing record must survive the loss of a field no command read."""

   def test_a_v1_record_migrates_and_forgets_its_task (self, repo_with_origin, tmp_path):
      _, feature = _start ("payments", _actor ("codex", "payments"))
      path = state.root () / "features" / f"{identity.key (feature ['feature_id'])}.json"
      record = json.loads (path.read_text ())
      record ["schema"] = "imp.feature.v1"
      record ["task"] = "Improve failed-payment recovery"
      path.write_text (json.dumps (record, indent=3, sort_keys=True) + "\n")

      stored = features.find ("payments")

      assert stored ["schema"] == "imp.feature.v2"
      assert "task" not in stored
      assert json.loads (path.read_text ()) ["schema"] == "imp.feature.v2"
