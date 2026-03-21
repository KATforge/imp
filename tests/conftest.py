import os
import subprocess
from pathlib import Path

import pytest

from imp import ai


@pytest.fixture
def repo (tmp_path):
   """Create a temporary git repo with one commit."""

   subprocess.run (
      [ "git", "init", "-b", "main" ],
      cwd=tmp_path,
      check=True,
      capture_output=True,
   )

   subprocess.run (
      [ "git", "config", "user.email", "test@test.com" ],
      cwd=tmp_path,
      check=True,
      capture_output=True,
   )

   subprocess.run (
      [ "git", "config", "user.name", "Test" ],
      cwd=tmp_path,
      check=True,
      capture_output=True,
   )

   (tmp_path / "file.txt").write_text ("hello\n")

   subprocess.run (
      [ "git", "add", "file.txt" ],
      cwd=tmp_path,
      check=True,
      capture_output=True,
   )

   subprocess.run (
      [ "git", "commit", "-m", "Initial commit" ],
      cwd=tmp_path,
      check=True,
      capture_output=True,
   )

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
