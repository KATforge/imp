import subprocess

import pytest
import typer

from imp import ai, console, git
from imp.commands import branch as branch_cmd
from imp.commands import commit as commit_cmd
from imp.commands import push as push_mod
from imp.commands import review as review_cmd


class TestCommitCommand:

   def test_commits_with_ai_message (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)

      commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

      result = subprocess.run (
         [ "git", "log", "-1", "--format=%s" ],
         cwd=repo, capture_output=True, text=True,
      )
      assert result.stdout.strip () == "feat: add login"

   def test_commit_all_stages_everything (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add feature")
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      (repo / "new.txt").write_text ("new file\n")

      commit_cmd.commit (all=True, exclude=None, yes=False, push=False, whisper="")

      result = subprocess.run (
         [ "git", "log", "-1", "--format=%s" ],
         cwd=repo, capture_output=True, text=True,
      )
      assert result.stdout.strip () == "feat: add feature"

   def test_commit_cancelled (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "No")

      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)

      with pytest.raises (typer.Exit):
         commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

      assert git.commit_count () == 1

   def test_commit_nothing_staged (self, repo, monkeypatch):
      with pytest.raises (typer.Exit):
         commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

   def test_commit_push_calls_do_push (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      pushed = []
      monkeypatch.setattr (push_mod, "do_push", lambda: pushed.append (True))

      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)

      commit_cmd.commit (all=False, exclude=None, yes=False, push=True, whisper="")

      assert len (pushed) == 1

   def test_commit_push_skipped_on_cancel (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "No")

      pushed = []
      monkeypatch.setattr (push_mod, "do_push", lambda: pushed.append (True))

      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)

      with pytest.raises (typer.Exit):
         commit_cmd.commit (all=False, exclude=None, yes=False, push=True, whisper="")

      assert len (pushed) == 0

   def test_commit_no_push_by_default (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      pushed = []
      monkeypatch.setattr (push_mod, "do_push", lambda: pushed.append (True))

      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)

      commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

      assert len (pushed) == 0

   def test_commit_retries_on_invalid_ai (self, repo, monkeypatch):
      calls = []

      def mock_fast (prompt):
         calls.append (1)
         if len (calls) == 1:
            return "GARBAGE"
         return "fix: resolve bug"

      monkeypatch.setattr (ai, "fast", mock_fast)
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)

      commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

      result = subprocess.run (
         [ "git", "log", "-1", "--format=%s" ],
         cwd=repo, capture_output=True, text=True,
      )
      assert result.stdout.strip () == "fix: resolve bug"
      assert len (calls) == 2


class TestBranchCommand:

   def test_creates_branch (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat/user-auth")
      monkeypatch.setattr (console, "confirm", lambda msg: True)

      branch_cmd._create ("add user authentication")

      assert git.branch () == "feat/user-auth"

   def test_create_cancelled (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat/user-auth")
      monkeypatch.setattr (console, "confirm", lambda msg: False)

      with pytest.raises (typer.Exit):
         branch_cmd._create ("add user authentication")

      assert git.branch () == "main"

   def test_rejects_invalid_name (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "invalid branch name!")

      with pytest.raises (typer.Exit):
         branch_cmd._create ("something")


class TestReviewCommand:

   def test_reviews_staged_changes (self, repo, monkeypatch):
      captured = {}

      def mock_smart (prompt):
         captured ["prompt"] = prompt
         return "Code looks good. No issues found."

      monkeypatch.setattr (ai, "smart", mock_smart)
      monkeypatch.setattr (
         console, "spin",
         lambda title, fn, *args: fn (*args),
      )

      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)

      review_cmd.review ()

      assert "prompt" in captured
      assert "changed" in captured ["prompt"]

   def test_review_no_changes (self, repo):
      with pytest.raises (typer.Exit):
         review_cmd.review ()


class TestStatusParsing:

   def test_path_not_truncated (self, repo):
      """Regression: line[2:].lstrip(' ') must not strip path characters."""

      (repo / "settings.py").write_text ("CONFIG = True\n")

      raw = git.status_short ()
      for line in raw.splitlines ():
         if len (line) < 4:
            continue
         path = line [2:].lstrip (" ")
         assert path == "settings.py", f"Path was truncated to '{path}'"

   def test_modified_path_preserved (self, repo):
      """Paths starting with space-like chars survive lstrip(' ')."""

      (repo / "  spaced.txt").write_text ("edge case\n")

      raw = git.status_short ()
      found = False
      for line in raw.splitlines ():
         if len (line) < 4:
            continue
         path = line [2:].lstrip (" ")
         if "spaced.txt" in path:
            found = True
      assert found, "File with leading spaces not found in status"
