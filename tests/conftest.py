import os
import subprocess
from pathlib import Path

import pytest

from imp import ai, console


def git_run (cwd, *args):
   return subprocess.run (
      [ "git", *args ],
      cwd=cwd,
      check=True,
      capture_output=True,
      text=True,
   )


def commit_file (repo, name, content, message):
   (repo / name).write_text (content)
   git_run (repo, "add", name)
   git_run (repo, "commit", "-m", message)


def last_commit_subject (repo):
   result = git_run (repo, "log", "-1", "--format=%s")
   return result.stdout.strip ()


@pytest.fixture
def repo (tmp_path):
   """Create a temporary git repo with one commit."""

   git_run (tmp_path, "init", "-b", "main")
   git_run (tmp_path, "config", "user.email", "test@test.com")
   git_run (tmp_path, "config", "user.name", "Test")
   commit_file (tmp_path, "file.txt", "hello\n", "Initial commit")

   old_cwd = Path.cwd ()
   os.chdir (tmp_path)
   yield tmp_path
   os.chdir (old_cwd)


@pytest.fixture
def mock_ai (monkeypatch):
   """Return a function that sets a canned AI response."""

   def _mock (response: str):
      monkeypatch.setattr (ai, "_call", lambda prompt, model: response)

   return _mock


@pytest.fixture
def mock_spin (monkeypatch):
   """Bypass console.spin, call function directly."""
   monkeypatch.setattr (console, "spin", lambda title, fn, *args, **kwargs: fn (*args, **kwargs))


@pytest.fixture
def repo_with_origin (tmp_path):
   """Repo with an 'origin' remote pointing at a bare clone; primary branch 'master'.

   Mirrors a real working clone: there's a local 'master' tracking 'origin/master',
   plus a feature branch 'feat/wip' checked out at HEAD with a divergent commit.
   Used to verify worktree-add defaults branch off origin/master, not whatever
   feature branch the host worktree happens to be on.
   """

   origin = tmp_path / "origin.git"
   work = tmp_path / "work"

   git_run (tmp_path, "init", "--bare", "-b", "master", str (origin))

   git_run (tmp_path, "init", "-b", "master", str (work))
   git_run (work, "config", "user.email", "test@test.com")
   git_run (work, "config", "user.name", "Test")
   commit_file (work, "file.txt", "trunk\n", "Initial commit")
   git_run (work, "remote", "add", "origin", str (origin))
   git_run (work, "push", "-u", "origin", "master")

   git_run (work, "checkout", "-b", "feat/wip")
   commit_file (work, "wip.txt", "wip\n", "feat: wip work")

   old_cwd = Path.cwd ()
   os.chdir (work)
   yield work
   os.chdir (old_cwd)
