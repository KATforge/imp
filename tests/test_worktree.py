from pathlib import Path

import pytest
import typer

from imp_git import features, git, runtime
from imp_git.commands import start as start_cmd
from imp_git.commands import worktree as worktree_cmd
from tests.conftest import commit_file, git_run


class TestStart:

   def test_uses_remote_trunk_not_head (self, repo_with_origin, mock_spin):
      start_cmd.start (name="payment")

      assert git.rev_parse ("feature/payment") == git.rev_parse ("origin/master")
      assert git.rev_parse ("feature/payment") != git.rev_parse ("HEAD")

   def test_fetches_remote_trunk (self, repo_with_origin, tmp_path, mock_spin):
      other = tmp_path / "other"
      git_run (tmp_path, "clone", str (tmp_path / "origin.git"), str (other))
      git_run (other, "config", "user.email", "t@t.com")
      git_run (other, "config", "user.name", "T")
      commit_file (other, "remote.txt", "remote\n", "feat: remote work")
      git_run (other, "push", "origin", "master")

      start_cmd.start (name="fresh")

      assert git.rev_parse ("feature/fresh") == git_run (other, "rev-parse", "HEAD").stdout.strip ()

   def test_uses_local_trunk_when_ahead (self, repo_with_origin, mock_spin):
      git_run (repo_with_origin, "checkout", "master")
      commit_file (repo_with_origin, "landed.txt", "landed\n", "feat: landed")

      start_cmd.start (name="next", worktree=True)

      assert git.rev_parse ("feature/next") == git.rev_parse ("master")

   def test_uses_main (self, repo, tmp_path, mock_spin):
      origin = tmp_path / "origin-main.git"
      git_run (repo, "init", "--bare", "-b", "main", str (origin))
      git_run (repo, "remote", "add", "origin", str (origin))
      git_run (repo, "push", "-u", "origin", "main")

      start_cmd.start (name="main-base", worktree=True)

      assert git.rev_parse ("feature/main-base") == git.rev_parse ("origin/main")

   def test_uses_local_trunk_without_remote (self, repo, mock_spin):
      git_run (repo, "checkout", "-b", "feat/wip")
      commit_file (repo, "wip.txt", "wip\n", "feat: wip")

      start_cmd.start (name="local")

      assert git.rev_parse ("feature/local") == git.rev_parse ("main")

   def test_requires_trunk (self, tmp_path, mock_spin, monkeypatch):
      work = tmp_path / "naked"
      git_run (tmp_path, "init", "-b", "feat/only", str (work))
      git_run (work, "config", "user.email", "t@t.com")
      git_run (work, "config", "user.name", "T")
      commit_file (work, "file.txt", "x\n", "init")
      monkeypatch.chdir (work)

      with pytest.raises (typer.Exit):
         start_cmd.start (name="doomed")

   def test_ticket_shapes_the_branch (self, repo_with_origin, mock_spin):
      start_cmd.start (name="payment retries", ticket="spk-12345")

      assert git.ref_exists ("feature/SPK-12345-payment-retries")
      feature = features.find ("payment-retries")
      assert feature ["ticket"] == "SPK-12345"

   def test_invalid_ticket_is_refused (self, repo_with_origin, mock_spin):
      with pytest.raises (typer.Exit):
         start_cmd.start (name="payment", ticket="not a ticket")


def test_worktree_path (repo_with_origin, tmp_path, mock_spin):
   start_cmd.start (name="path")
   feature = features.find ("path")

   assert worktree_cmd.path ("path") == feature ["path"]


def test_worktree_remove (repo_with_origin, tmp_path, mock_spin):
   runtime.configure (yes=True)
   start_cmd.start (name="discard")
   feature = features.find ("discard")

   result = worktree_cmd.remove ("discard")

   assert result ["branch"] == "feature/discard"
   assert result ["attic"].startswith ("refs/imp/attic/discard/")
   assert not Path (feature ["path"]).exists ()
   assert not git.ref_exists ("feature/discard")
   assert features.find ("discard") is None
