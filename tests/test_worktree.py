import pytest
import typer

from imp import git
from imp.commands import worktree as worktree_cmd
from tests.conftest import commit_file, git_run


class TestWorktreeAddSafeBase:
   """`imp worktree add` MUST root the new branch at origin/<trunk>, never at HEAD.

   Regression: KAT-35 + KAT-36 — both Maiev instances had `imp worktree create`
   inherit the host worktree's HEAD (a feature branch) instead of master. KAT-36
   squash-merged unrelated work to master and required a revert. The default
   MUST fetch origin and branch off origin/<trunk>.
   """

   def test_defaults_to_origin_master_not_head (self, repo_with_origin, tmp_path, mock_spin):
      """HEAD is on feat/wip; new branch MUST root at origin/master, not feat/wip."""

      wt_path = tmp_path / "new-wt"

      assert git.branch () == "feat/wip"

      worktree_cmd.add (
         name="KAT-99-thing",
         base="",
         path=str (wt_path),
         no_fetch=False,
      )

      assert wt_path.exists ()

      origin_master_sha = git.rev_parse ("origin/master")
      new_branch_sha = git.rev_parse ("KAT-99-thing")

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

      worktree_cmd.add (
         name="KAT-99-fetched",
         base="",
         path=str (tmp_path / "fetched-wt"),
         no_fetch=False,
      )

      assert any (
         kwargs.get ("remote") == "origin" and kwargs.get ("refspec") == "master"
         for _args, kwargs in fetched
      ), f"expected fetch(origin, master); got {fetched}"

   def test_no_fetch_skips_network (self, repo_with_origin, tmp_path, mock_spin, monkeypatch):
      """--no-fetch trusts the local origin/master ref, skips the fetch call."""

      fetched = []
      monkeypatch.setattr (git, "fetch", lambda *a, **k: fetched.append ((a, k)))

      worktree_cmd.add (
         name="KAT-99-cached",
         base="",
         path=str (tmp_path / "cached-wt"),
         no_fetch=True,
      )

      assert fetched == []

   def test_explicit_base_uses_that_ref (self, repo_with_origin, tmp_path, mock_spin):
      """--base <ref> roots at that ref exactly, regardless of HEAD or origin."""

      target_sha = git.rev_parse ("feat/wip")
      wt_path = tmp_path / "explicit-wt"

      worktree_cmd.add (
         name="KAT-99-explicit",
         base="feat/wip",
         path=str (wt_path),
         no_fetch=False,
      )

      assert git.rev_parse ("KAT-99-explicit") == target_sha

   def test_explicit_base_does_not_fetch (self, repo_with_origin, tmp_path, mock_spin, monkeypatch):
      """--base is an explicit choice; we don't second-guess with a fetch."""

      fetched = []
      monkeypatch.setattr (git, "fetch", lambda *a, **k: fetched.append ((a, k)))

      worktree_cmd.add (
         name="KAT-99-explicit-no-fetch",
         base="feat/wip",
         path=str (tmp_path / "explicit-no-fetch-wt"),
         no_fetch=False,
      )

      assert fetched == []

   def test_picks_main_when_master_absent (self, repo, tmp_path, mock_spin):
      """base_branch resolution picks 'main' when 'master' doesn't exist."""

      origin = tmp_path / "origin-main.git"
      git_run (repo, "init", "--bare", "-b", "main", str (origin))
      git_run (repo, "remote", "add", "origin", str (origin))
      git_run (repo, "push", "-u", "origin", "main")

      wt_path = tmp_path / "main-wt"

      worktree_cmd.add (
         name="KAT-99-main-base",
         base="",
         path=str (wt_path),
         no_fetch=False,
      )

      assert git.rev_parse ("KAT-99-main-base") == git.rev_parse ("origin/main")

   def test_falls_back_to_local_trunk_when_no_remote (self, repo, tmp_path, mock_spin):
      """No remote configured: fall back to local trunk branch, never HEAD."""

      git.checkout ("feat/local-wip", create=True)
      commit_file (repo, "wip.txt", "wip\n", "feat: wip")

      assert git.branch () == "feat/local-wip"
      main_sha = git.rev_parse ("main")
      head_sha = git.rev_parse ("HEAD")
      assert main_sha != head_sha

      wt_path = tmp_path / "no-remote-wt"

      worktree_cmd.add (
         name="KAT-99-no-remote",
         base="",
         path=str (wt_path),
         no_fetch=False,
      )

      assert git.rev_parse ("KAT-99-no-remote") == main_sha

   def test_aborts_when_no_remote_and_no_local_trunk (self, tmp_path, mock_spin, monkeypatch):
      """No remote AND no local trunk: refuse, don't silently pick HEAD."""

      work = tmp_path / "naked"
      git_run (tmp_path, "init", "-b", "feat/only", str (work))
      git_run (work, "config", "user.email", "t@t.com")
      git_run (work, "config", "user.name", "T")
      commit_file (work, "file.txt", "x\n", "init")

      monkeypatch.chdir (work)

      with pytest.raises (typer.Exit):
         worktree_cmd.add (
            name="KAT-99-doomed",
            base="",
            path=str (tmp_path / "doomed-wt"),
            no_fetch=False,
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
