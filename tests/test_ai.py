import json

import pytest
import typer

from imp_git import ai


class _Response:

   def __enter__ (self):
      return self

   def __exit__ (self, *_):
      return None

   def read (self):
      return b'{"response": "OK"}'


class TestOllama:

   def test_disables_thinking (self, monkeypatch):
      payload = {}

      def urlopen (request, timeout):
         payload.update (json.loads (request.data))
         return _Response ()

      monkeypatch.setattr (ai.urllib.request, "urlopen", urlopen)

      assert ai._ollama ("Reply with OK", "qwen3:8b") == "OK"
      assert payload ["think"] is False


class TestOneline:

   def test_strips_newlines (self):
      assert ai.oneline ("hello\nworld\n") == "helloworld"

   def test_strips_whitespace (self):
      assert ai.oneline ("  hello  ") == "hello"

   def test_empty (self):
      assert ai.oneline ("") == ""

   def test_only_newlines (self):
      assert ai.oneline ("\n\n\n") == ""


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


class TestGuard:

   def test_adds_authorship_rule (self, monkeypatch):
      captured = {}
      monkeypatch.setattr (ai.config, "get", lambda key: "test-model")
      monkeypatch.setattr (ai, "_call", lambda prompt, model: captured.update (prompt=prompt) or "OK")

      assert ai.fast ("Do the task", spin=False) == "OK"
      assert "Never identify an AI agent" in captured ["prompt"]
      assert "actor IDs" in captured ["prompt"]


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
