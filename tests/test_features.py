import os
from pathlib import Path

import pytest

from imp_git import ai, commit_plan, features, git, state
from tests.conftest import git_run


def _start (name, ticket=""):
   plan = features.plan_start (name, ticket=ticket)
   return plan, features.apply_start (plan)


class TestDerivation:

   def test_a_feature_is_its_branch_and_worktree (self, repo_with_origin):
      _plan, feature = _start ("payments")

      derived = features.find ("payments")

      assert derived ["branch"] == "feature/payments"
      assert derived ["path"] == feature ["path"]
      assert derived ["worktree_state"] == "live"
      assert derived ["created_at"]

   def test_nothing_is_written_outside_git (self, repo_with_origin):
      _start ("payments")

      common = Path (git.capture ("rev-parse", "--git-common-dir").strip ())

      assert not (common / "imp").exists ()

   def test_the_primary_checkout_is_never_a_feature (self, repo_with_origin):
      git_run (repo_with_origin, "checkout", "-b", "feature/manual")

      assert features.find ("manual") ["worktree_state"] == "branch-only"

   def test_a_branch_without_a_worktree_is_branch_only (self, repo_with_origin):
      git_run (repo_with_origin, "branch", "feature/parked", "master")

      derived = features.find ("parked")

      assert derived ["worktree_state"] == "branch-only"
      assert derived ["path"] == ""

   def test_ticket_prefix_derives_name_and_ticket (self, repo_with_origin):
      _start ("payments", ticket="SPK-12345")

      derived = features.find ("payments")

      assert derived ["branch"] == "feature/SPK-12345-payments"
      assert derived ["ticket"] == "SPK-12345"
      assert features.find ("feature/SPK-12345-payments") == derived

   def test_missing_ticket_warns_when_convention_exists (self, repo_with_origin):
      _start ("payments", ticket="SPK-1")

      plan = features.plan_start ("profile")

      assert any ("ticket" in warning for warning in plan ["warnings"])


class TestStart:

   def test_start_plan_is_read_only_and_uses_fresh_remote_trunk (self, repo_with_origin, tmp_path):
      plan = features.plan_start ("payments")

      assert not git.ref_exists ("feature/payments")

      feature = features.apply_start (plan)

      assert plan ["payload"] ["base:oid"] == git.rev_parse ("origin/master")
      assert git.rev_parse ("feature/payments") == git.rev_parse ("origin/master")
      assert not (Path (feature ["path"]) / "wip.txt").exists ()

   def test_two_agents_commit_in_isolated_worktrees (self, repo_with_origin, monkeypatch):
      _first_plan, first = _start ("payments")
      _second_plan, second = _start ("profile")
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add isolated marker")

      monkeypatch.chdir (first ["path"])
      Path ("payments.txt").write_text ("payments\n")
      commit_plan.apply (commit_plan.create ())

      monkeypatch.chdir (second ["path"])
      Path ("profile.txt").write_text ("profile\n")
      commit_plan.apply (commit_plan.create ())

      assert git.capture ("show", "feature/payments:payments.txt").strip () == "payments"
      assert not git.succeeds ("cat-file", "-e", "feature/payments:profile.txt")
      assert git.capture ("show", "feature/profile:profile.txt").strip () == "profile"
      assert not git.succeeds ("cat-file", "-e", "feature/profile:payments.txt")

   def test_feature_worktree_does_not_disturb_the_current_branch (self, repo_with_origin):
      original_branch = git.branch ()

      _plan, feature = _start ("payments")

      assert Path (feature ["path"]).is_dir ()
      assert git.branch () == original_branch

   def test_duplicate_feature_is_refused (self, repo_with_origin):
      _start ("payments")

      with pytest.raises (state.StateError, match="already exists"):
         features.plan_start ("payments")


class TestRemoval:

   def test_clean_worktree_removal_parks_the_tip_in_the_attic (self, repo_with_origin):
      _start_plan, feature = _start ("temporary")

      plan = features.plan_remove (feature)
      result = features.apply_remove (plan)

      assert result ["attic"].startswith ("refs/imp/attic/temporary/")
      assert git.rev_parse (result ["attic"])
      assert not Path (feature ["path"]).exists ()
      assert features.find ("temporary") is None

   def test_dirty_worktree_removal_is_blocked (self, repo_with_origin):
      _plan, feature = _start ("dirty")
      (Path (feature ["path"]) / "loose.txt").write_text ("unsaved\n")

      plan = features.plan_remove (features.find ("dirty"))

      assert plan ["state"] == "blocked"
      assert any ("uncommitted" in blocker for blocker in plan ["blockers"])

   def test_completing_from_inside_the_worktree_leaves_a_live_directory (self, repo_with_origin):
      _plan, feature = _start ("stepping")
      os.chdir (feature ["path"])

      features.complete (feature)

      assert Path.cwd ().exists ()
      assert not Path (feature ["path"]).exists ()
      assert features.find ("stepping") is None


class TestAttic:

   def test_expiry_removes_only_old_refs (self, repo_with_origin):
      oid = git.rev_parse ("master")
      git.update_ref_checked ("refs/imp/attic/old/20200101T000000Z", oid, "")
      git.update_ref_checked (f"refs/imp/attic/new/{state.stamp ()}", oid, "")

      removed = features.expire_attic ()

      assert removed == [ "refs/imp/attic/old/20200101T000000Z" ]
      assert len (git.refs ("refs/imp/attic")) == 1
