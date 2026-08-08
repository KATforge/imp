import pytest
import typer

from imp_git import ai, console, git
from imp_git.commands import commit as commit_cmd
from imp_git.commands import review as review_cmd
from tests.conftest import commit_count, commit_file, git_run, last_commit_subject


class TestCommitCommand:

   def test_commits_with_ai_message (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "confirm", lambda text: True)

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      commit_cmd.commit (all=False, exclude=None, yes=False, whisper="")

      assert last_commit_subject (repo) == "feat: add login"

   def test_commit_all_stages_everything (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add feature")
      monkeypatch.setattr (console, "confirm", lambda text: True)

      (repo / "new.txt").write_text ("new file\n")

      commit_cmd.commit (all=True, exclude=None, yes=False, whisper="")

      assert last_commit_subject (repo) == "feat: add feature"

   def test_commit_cancelled (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "confirm", lambda text: False)

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      with pytest.raises (typer.Exit):
         commit_cmd.commit (all=False, exclude=None, yes=False, whisper="")

      assert commit_count (repo) == 1

   def test_commit_nothing_staged (self, repo, monkeypatch):
      with pytest.raises (typer.Exit):
         commit_cmd.commit (all=False, exclude=None, yes=False, whisper="")

   def test_commit_retries_on_invalid_ai (self, repo, monkeypatch):
      calls = []

      def mock_fast (prompt):
         calls.append (1)
         if len (calls) == 1:
            return "GARBAGE"
         return "fix: resolve bug"

      monkeypatch.setattr (ai, "fast", mock_fast)
      monkeypatch.setattr (console, "confirm", lambda text: True)

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      commit_cmd.commit (all=False, exclude=None, yes=False, whisper="")

      assert last_commit_subject (repo) == "fix: resolve bug"
      assert len (calls) == 2


class TestReviewCommand:

   def test_reviews_staged_changes (self, repo, monkeypatch, mock_spin):
      captured = {}

      def mock_smart (prompt, spin=True):
         captured ["prompt"] = prompt
         return "Code looks good. No issues found."

      monkeypatch.setattr (ai, "smart", mock_smart)

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      review_cmd.review (last=0, whisper="")

      assert "prompt" in captured
      assert "changed" in captured ["prompt"]

   def test_reviews_last_n_commits (self, repo, monkeypatch, mock_spin):
      captured = {}

      def mock_smart (prompt, spin=True):
         captured ["prompt"] = prompt
         return "Code looks good. No issues found."

      monkeypatch.setattr (ai, "smart", mock_smart)

      commit_file (repo, "file.txt", "first\n", "first")
      commit_file (repo, "file.txt", "second\n", "second")

      review_cmd.review (last=2, whisper="")

      assert "prompt" in captured
      assert "second" in captured ["prompt"]

   def test_review_no_changes (self, repo):
      with pytest.raises (typer.Exit):
         review_cmd.review (last=0, whisper="")


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
         if "spaced" in path:
            found = True
      assert found, "File with leading spaces not found in status"
