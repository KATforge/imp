import subprocess

import pytest
import typer

from imp import git


class TestRequire:

   def test_passes_in_repo (self, repo):
      git.require ()

   def test_fails_outside_repo (self, tmp_path, monkeypatch):
      monkeypatch.chdir (tmp_path)
      with pytest.raises (typer.Exit):
         git.require ()


class TestDiff:

   def test_empty_when_clean (self, repo):
      assert git.diff (staged=True) == ""

   def test_staged_changes (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "file.txt" ], cwd=repo, check=True)
      assert "changed" in git.diff (staged=True)

   def test_unstaged_changes (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      assert "changed" in git.diff ()


class TestBranch:

   def test_returns_current (self, repo):
      assert git.branch () == "main"


class TestStage:

   def test_stage_all (self, repo):
      (repo / "new.txt").write_text ("new\n")
      git.stage (all=True)
      result = subprocess.run (
         [ "git", "diff", "--cached", "--name-only" ],
         cwd=repo,
         capture_output=True,
         text=True,
      )
      assert "new.txt" in result.stdout


class TestIsClean:

   def test_clean_repo (self, repo):
      assert git.is_clean ()

   def test_dirty_repo (self, repo):
      (repo / "file.txt").write_text ("dirty\n")
      assert not git.is_clean ()


class TestBaseBranch:

   def test_returns_main (self, repo):
      assert git.base_branch () == "main"

   def test_returns_master (self, repo):
      subprocess.run (
         [ "git", "branch", "-m", "main", "master" ],
         cwd=repo,
         check=True,
         capture_output=True,
      )
      assert git.base_branch () == "master"
