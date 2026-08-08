import json
import socket
import subprocess
import sys

import pytest
import typer

from imp_git import features, git, plans, state
from imp_git.commands import start as start_cmd
from imp_git.commands import worktree as worktree_cmd
from tests.conftest import commit_file, git_run


class TestStartSafeBase:
   """`imp start` MUST root the new branch at origin/<trunk>, never at HEAD.

   Regression: KAT-35 + KAT-36 — both Maiev instances had `imp worktree create`
   inherit the host worktree's HEAD (a feature branch) instead of master. KAT-36
   squash-merged unrelated work to master and required a revert. The default
   MUST fetch origin and branch off origin/<trunk>.
   """

   def test_defaults_to_origin_master_not_head (self, repo_with_origin, tmp_path, mock_spin):
      """HEAD is on feat/wip; new branch MUST root at origin/master, not feat/wip."""

      wt_path = tmp_path / "new-wt"

      assert git.branch () == "feat/wip"

      start_cmd.start (
         name="KAT-99-thing",
         base="",
         path=str (wt_path),
         yes=True,
      )

      assert wt_path.exists ()

      origin_master_sha = git.rev_parse ("origin/master")
      new_branch_sha = git.rev_parse ("feature/kat-99-thing")

      assert new_branch_sha == origin_master_sha, (
         "new branch was rooted at HEAD (feat/wip), not origin/master — "
         "this is the KAT-36 bug"
      )

      head_sha = git.rev_parse ("HEAD")
      assert new_branch_sha != head_sha

   def test_default_fetches_origin (self, repo_with_origin, tmp_path, mock_spin, monkeypatch):
      """Default path calls git.fetch with origin + trunk refspec."""

      fetched = []
      real_fetch = git.fetch

      def spy_fetch (*args, **kwargs):
         fetched.append ((args, kwargs))
         return real_fetch (*args, **kwargs)

      monkeypatch.setattr (git, "fetch", spy_fetch)

      start_cmd.start (
         name="KAT-99-fetched",
         base="",
         path=str (tmp_path / "fetched-wt"),
         yes=True,
      )

      assert any (
         kwargs.get ("remote") == "origin"
         and kwargs.get ("refspec") == "+refs/heads/master:refs/remotes/origin/master"
         for _args, kwargs in fetched
      ), f"expected fetch(origin, master); got {fetched}"

   def test_explicit_base_uses_that_ref (self, repo_with_origin, tmp_path, mock_spin):
      """--base <ref> roots at that ref exactly, regardless of HEAD or origin."""

      target_sha = git.rev_parse ("feat/wip")
      wt_path = tmp_path / "explicit-wt"

      start_cmd.start (
         name="KAT-99-explicit",
         base="feat/wip",
         path=str (wt_path),
         yes=True,
      )

      assert git.rev_parse ("feature/kat-99-explicit") == target_sha

   def test_explicit_base_does_not_fetch (self, repo_with_origin, tmp_path, mock_spin, monkeypatch):
      """--base is an explicit choice; we don't second-guess with a fetch."""

      fetched = []
      monkeypatch.setattr (git, "fetch", lambda *a, **k: fetched.append ((a, k)))

      start_cmd.start (
         name="KAT-99-explicit-no-fetch",
         base="feat/wip",
         path=str (tmp_path / "explicit-no-fetch-wt"),
         yes=True,
      )

      assert fetched == []

   def test_picks_main_when_master_absent (self, repo, tmp_path, mock_spin):
      """base_branch resolution picks 'main' when 'master' doesn't exist."""

      origin = tmp_path / "origin-main.git"
      git_run (repo, "init", "--bare", "-b", "main", str (origin))
      git_run (repo, "remote", "add", "origin", str (origin))
      git_run (repo, "push", "-u", "origin", "main")

      wt_path = tmp_path / "main-wt"

      start_cmd.start (
         name="KAT-99-main-base",
         base="",
         path=str (wt_path),
         yes=True,
      )

      assert git.rev_parse ("feature/kat-99-main-base") == git.rev_parse ("origin/main")

   def test_falls_back_to_local_trunk_when_no_remote (self, repo, tmp_path, mock_spin):
      """No remote configured: fall back to local trunk branch, never HEAD."""

      git_run (repo, "checkout", "-b", "feat/local-wip")
      commit_file (repo, "wip.txt", "wip\n", "feat: wip")

      assert git.branch () == "feat/local-wip"
      main_sha = git.rev_parse ("main")
      head_sha = git.rev_parse ("HEAD")
      assert main_sha != head_sha

      wt_path = tmp_path / "no-remote-wt"

      start_cmd.start (
         name="KAT-99-no-remote",
         base="",
         path=str (wt_path),
         yes=True,
      )

      assert git.rev_parse ("feature/kat-99-no-remote") == main_sha

   def test_aborts_when_no_remote_and_no_local_trunk (self, tmp_path, mock_spin, monkeypatch):
      """No remote AND no local trunk: refuse, don't silently pick HEAD."""

      work = tmp_path / "naked"
      git_run (tmp_path, "init", "-b", "feat/only", str (work))
      git_run (work, "config", "user.email", "t@t.com")
      git_run (work, "config", "user.name", "T")
      commit_file (work, "file.txt", "x\n", "init")

      monkeypatch.chdir (work)

      with pytest.raises (typer.Exit):
         start_cmd.start (
            name="KAT-99-doomed",
            base="",
            path=str (tmp_path / "doomed-wt"),
            yes=True,
         )


class TestRefExists:

   def test_existing_ref (self, repo):
      assert git.ref_exists ("HEAD") is True

   def test_missing_ref (self, repo):
      assert git.ref_exists ("nope/not/here") is False


class TestFetchRemoteRefspec:

   def test_fetches_specific_refspec (self, repo_with_origin):
      """fetch(remote, refspec) translates to `git fetch <remote> <refspec>`."""

      origin_master_before = git.rev_parse ("origin/master")
      git.fetch (remote="origin", refspec="master")
      origin_master_after = git.rev_parse ("origin/master")

      assert origin_master_after == origin_master_before


class TestPruneReconciliation:

   def test_orphaned_managed_worktree_is_reported_then_removed (self, repo_with_origin, tmp_path):
      orphan = tmp_path / "orphan-wt"
      git_run (repo_with_origin, "worktree", "add", "-b", "feature/orphan", str (orphan), "origin/master")

      report = worktree_cmd.prune ()
      assert [ value ["branch"] for value in report ["orphans"] ] == [ "feature/orphan" ]
      assert orphan.exists ()

      removed = worktree_cmd.prune (remove_orphans=True)
      assert removed ["removed"]
      assert not orphan.exists ()
      assert "feature/orphan" not in git.branches_local ()

   def test_orphaned_managed_worktree_can_be_adopted (self, repo_with_origin, tmp_path):
      orphan = tmp_path / "adopt-wt"
      git_run (repo_with_origin, "worktree", "add", "-b", "feature/adopt-me", str (orphan), "origin/master")

      report = worktree_cmd.prune (adopt=True, actor_id="actor:human:test")

      assert report ["adopted"] == [ "feature:adopt-me" ]
      feature = features.find ("adopt-me")
      assert feature is not None
      assert feature ["worktree_state"] == "live"

   def test_stale_ready_start_plan_is_marked_failed (self, repo_with_origin, tmp_path):
      plan = features.plan_start (
         "ghost",
         actor_id="actor:human:test",
         path=str (tmp_path / "ghost-wt"),
      )
      payload = plan ["payload"]
      git_run (
         repo_with_origin,
         "worktree", "add", "-b", str (payload ["branch"]), str (payload ["path"]), str (payload ["base:oid"]),
      )

      worktree_cmd.prune (remove_orphans=True)

      assert plans.load (plan ["plan_id"]) ["state"] == "failed"


class TestUnmanagedRemove:

   def test_remove_unmanaged_worktree_and_branch (self, repo_with_origin, tmp_path):
      target = tmp_path / "scratch-wt"
      git_run (repo_with_origin, "worktree", "add", "-b", "scratch", str (target), "origin/master")
      assert target.exists ()

      data = worktree_cmd.remove (name="scratch", unmanaged=True, delete_branch=True, yes=True)

      assert data ["unmanaged"] is True
      assert not target.exists ()
      assert "scratch" not in git.branches_local ()

   def test_unmanaged_remove_refuses_managed_worktrees (self, repo_with_origin, tmp_path, mock_spin):
      start_cmd.start (
         name="managed-one",
         path=str (tmp_path / "managed-wt"),
         yes=True,
         actor_id="actor:human:test",
      )

      with pytest.raises (typer.Exit):
         worktree_cmd.remove (name="managed-one", unmanaged=True, yes=True)


class TestLockScoping:

   def test_worktree_remove_ignores_the_global_features_lock (self, repo_with_origin, tmp_path, mock_spin):
      start_cmd.start (
         name="scoped",
         path=str (tmp_path / "scoped-wt"),
         yes=True,
         actor_id="actor:human:test",
      )
      feature = features.find ("scoped")
      child = subprocess.Popen ([ sys.executable, "-c", "import time; time.sleep(60)" ])
      path = state.root () / "locks" / "features.json"
      try:
         path.parent.mkdir (parents=True, exist_ok=True)
         path.write_text (json.dumps ({
            "schema": "imp.lock.v1",
            "name": "features",
            "pid": child.pid,
            "host": socket.gethostname (),
            "started_at": state.now (),
         }, indent=3, sort_keys=True) + "\n")

         plan = features.plan_remove (feature, actor_id="actor:human:test")
         data = features.apply_remove (plan, "actor:human:test")

         assert data ["feature_id"] == feature ["feature_id"]
      finally:
         child.kill ()
         child.wait ()
         path.unlink (missing_ok=True)
