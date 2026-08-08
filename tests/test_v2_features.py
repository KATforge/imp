import json
import sys
from pathlib import Path

import pytest

from imp_git import ai, commit_plan, features, git, identity, state
from imp_git import repo as repo_mod
from imp_git.commands import context as context_cmd
from tests.conftest import git_run


def _actor (kind: str, name: str) -> str:
   return identity.resource ("actor", kind, name)


def _start (name, actor_id, path, *, use=False):
   plan = features.plan_start (name, actor_id=actor_id, path=str (path), use=use)
   return plan, features.apply_start (plan)


class TestManagedFeatures:

   def test_start_plan_is_read_only_and_uses_fresh_remote_trunk (self, repo_with_origin, tmp_path):
      actor_id = _actor ("codex", "payments")
      path = tmp_path / "payments"

      plan = features.plan_start ("payments", actor_id=actor_id, path=str (path))

      assert not path.exists ()
      assert not git.ref_exists ("feature/payments")
      assert plan ["payload"] ["base:oid"] == git.rev_parse ("origin/master")

      feature = features.apply_start (plan)

      assert feature ["feature_id"] == "feature:payments"
      assert feature ["claim"] ["held_by"] == actor_id
      assert git.rev_parse ("feature/payments") == git.rev_parse ("origin/master")
      assert not (path / "wip.txt").exists ()

   def test_temper_can_create_an_initially_unclaimed_feature (self, repo_with_origin, tmp_path):
      actor_id = _actor ("temper", "checkout")
      path = tmp_path / "checkout"
      plan = features.plan_start (
         "checkout",
         actor_id=actor_id,
         change_id="change:checkout",
         claim_writer=False,
         path=str (path),
         target="master",
      )

      feature = features.apply_start (plan)

      assert feature ["change_id"] == "change:checkout"
      assert feature ["claim"] is None
      assert feature ["target"] == "master"

   def test_two_agents_commit_in_isolated_worktrees (self, repo_with_origin, tmp_path, monkeypatch):
      first_actor = _actor ("codex", "payments")
      second_actor = _actor ("claude", "profile")
      _first_plan, first = _start ("payments", first_actor, tmp_path / "payments")
      _second_plan, second = _start ("profile", second_actor, tmp_path / "profile")
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add isolated marker")

      monkeypatch.chdir (first ["path"])
      Path ("payments.txt").write_text ("payments\n")
      first_commit = commit_plan.create (actor_id=first_actor, all_changes=True)
      commit_plan.apply (first_commit, first_actor)

      monkeypatch.chdir (second ["path"])
      Path ("profile.txt").write_text ("profile\n")
      second_commit = commit_plan.create (actor_id=second_actor, all_changes=True)
      commit_plan.apply (second_commit, second_actor)

      assert git.capture ("show", "feature/payments:payments.txt").strip () == "payments"
      assert not git.succeeds ("cat-file", "-e", "feature/payments:profile.txt")
      assert git.capture ("show", "feature/profile:profile.txt").strip () == "profile"
      assert not git.succeeds ("cat-file", "-e", "feature/profile:payments.txt")

   def test_claim_prevents_a_second_writer (self, repo_with_origin, tmp_path, monkeypatch):
      owner = _actor ("codex", "owner")
      intruder = _actor ("claude", "intruder")
      _plan, feature = _start ("claimed", owner, tmp_path / "claimed")
      monkeypatch.chdir (feature ["path"])

      with pytest.raises (state.StateError, match="claimed by"):
         features.assert_write_access (intruder)

      features.assert_write_access (owner)

      context = context_cmd.context (
         feature=feature ["feature_id"],
         json_output=False,
         actor_id=owner,
      )

      assert context ["feature_id"] == feature ["feature_id"]
      assert context ["claim"] ["held_by"] == owner

   def test_expired_claim_allows_a_new_writer (self, repo_with_origin, tmp_path):
      owner = _actor ("codex", "owner")
      intruder = _actor ("claude", "intruder")
      _plan, feature = _start ("claimed", owner, tmp_path / "claimed")
      claim_path = features._claim_path (feature ["feature_id"])
      record = state.read (claim_path, "imp.claim.v1")
      record ["expires_at"] = "2000-01-01T00:00:00Z"
      state.atomic_write (claim_path, record)

      claim = features.claim (feature, intruder)

      assert claim ["held_by"] == intruder
      assert intruder in features.find (feature ["feature_id"]) ["writers"]

   def test_active_selection_switches_without_checkout (self, repo_with_origin, tmp_path):
      original_branch = git.branch ()
      _plan, first = _start ("payments", _actor ("human", "anders"), tmp_path / "payments")
      selection = features.select (first)

      assert selection ["schema"] == "imp.active.v1"
      assert features.active () ["path"] == first ["path"]
      assert git.branch () == original_branch

      trunk = features.select (None)

      assert trunk ["feature_id"] is None
      assert trunk ["generation"] == selection ["generation"] + 1

   def test_setup_and_ignored_share_are_applied_from_the_plan (self, repo_with_origin, tmp_path):
      git_run (repo_with_origin, "checkout", "master")
      (repo_with_origin / ".gitignore").write_text (".env.local\n")
      (repo_with_origin / ".env.local").write_text ("TOKEN=local\n")
      (repo_with_origin / ".imp").write_text (json.dumps ({
         "schema": "imp.config.v1",
         "worktree:setup": [
            { "name": "marker", "run": [ sys.executable, "-c", "open('setup.ok', 'w').write('ok')" ] },
         ],
         "worktree:share": [ ".env.local" ],
      }))
      git_run (repo_with_origin, "add", ".gitignore", ".imp")
      git_run (repo_with_origin, "commit", "-m", "chore: configure worktrees")
      git_run (repo_with_origin, "push", "origin", "master")
      repo_mod.load.cache_clear ()
      target = tmp_path / "shared"

      plan, feature = _start ("shared", _actor ("human", "anders"), target)

      assert {item ["action"] for item in plan ["items"]} >= { "setup", "share" }
      assert (target / ".env.local").is_symlink ()
      assert (target / ".env.local").read_text () == "TOKEN=local\n"
      assert (target / "setup.ok").read_text () == "ok"
      assert feature ["worktree_state"] == "live"

   def test_clean_worktree_removal_is_planned_and_retains_feature_record (self, repo_with_origin, tmp_path):
      actor_id = _actor ("human", "anders")
      _start_plan, feature = _start ("temporary", actor_id, tmp_path / "temporary", use=True)

      plan = features.plan_remove (feature, actor_id=actor_id)

      assert Path (feature ["path"]).exists ()
      result = features.apply_remove (plan, actor_id)

      assert result ["feature_id"] == feature ["feature_id"]
      assert not Path (feature ["path"]).exists ()
      retained = features.find (feature ["feature_id"])
      assert retained ["state"] == "removed"
      assert retained ["worktree_state"] == "missing"
      assert retained ["claim"] is None
      assert features.selection () ["feature_id"] is None
