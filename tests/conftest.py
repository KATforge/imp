import os
import subprocess

import pytest


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

   old_cwd = os.getcwd ()
   os.chdir (tmp_path)
   yield tmp_path
   os.chdir (old_cwd)


@pytest.fixture
def mock_ai (monkeypatch):
   """Return a function that sets a canned AI response."""

   def _mock (response: str):
      fake_bin = os.path.join (os.environ.get ("TMPDIR", "/tmp"), "imp-test-bin")
      os.makedirs (fake_bin, exist_ok=True)

      script = os.path.join (fake_bin, "claude")
      with open (script, "w") as f:
         f.write (f"#!/bin/bash\nprintf '%s\\n' {repr (response)}\n")
      os.chmod (script, 0o755)

      monkeypatch.setenv ("PATH", f"{fake_bin}:{os.environ ['PATH']}")
      monkeypatch.setenv ("IMP_AI_PROVIDER", "claude")

   return _mock
