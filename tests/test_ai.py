import pytest
import typer

from imp import ai


class TestSanitize:

   def test_strips_newlines (self):
      assert ai.sanitize ("hello\nworld\n") == "helloworld"

   def test_strips_whitespace (self):
      assert ai.sanitize ("  hello  ") == "hello"

   def test_empty (self):
      assert ai.sanitize ("") == ""

   def test_only_newlines (self):
      assert ai.sanitize ("\n\n\n") == ""


class TestTruncate:

   def test_short_text_unchanged (self):
      text = "line1\nline2\nline3"
      assert ai.truncate (text, max_lines=10) == text

   def test_exact_limit (self):
      text = "\n".join (f"line{i}" for i in range (5))
      assert ai.truncate (text, max_lines=5) == text

   def test_over_limit (self):
      text = "\n".join (f"line{i}" for i in range (10))
      result = ai.truncate (text, max_lines=3)
      assert result == "line0\nline1\nline2"

   def test_empty (self):
      assert ai.truncate ("", max_lines=5) == ""

   def test_default_limit (self):
      assert ai.MAX_DIFF_LINES == 2000


class TestCommitMessage:

   def test_valid_on_first_try (self, repo, mock_ai):
      mock_ai ("feat: add login")
      msg = ai.commit_message ("some prompt")
      assert msg == "feat: add login"

   def test_retries_on_invalid (self, repo, monkeypatch):
      calls = []

      def mock_fast (prompt):
         calls.append (1)
         if len (calls) == 1:
            return "INVALID"
         return "feat: valid message"

      monkeypatch.setattr (ai, "fast", mock_fast)
      msg = ai.commit_message ("some prompt")
      assert msg == "feat: valid message"
      assert len (calls) == 2

   def test_exits_after_two_failures (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "INVALID")
      with pytest.raises (typer.Exit):
         ai.commit_message ("some prompt")

   def test_exits_on_empty (self, repo, mock_ai):
      mock_ai ("")
      with pytest.raises (typer.Exit):
         ai.commit_message ("some prompt")
