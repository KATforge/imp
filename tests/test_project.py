from typer.main import get_command
from typer.testing import CliRunner

from imp_git import config, identity
from imp_git.main import app
from tests.conftest import git_run


class TestConfiguration:

   def test_defaults_need_no_configuration (self, repo):
      assert config.get ("provider") == "claude"
      assert config.get ("fastmodel") == "haiku"
      assert config.get ("smartmodel") == "sonnet"

   def test_git_config_overrides_defaults (self, repo):
      git_run (repo, "config", "imp.provider", "ollama")

      assert config.get ("provider") == "ollama"
      assert config.snapshot () ["provider"] == "ollama"

   def test_check_commands_are_multi_valued (self, repo):
      git_run (repo, "config", "--add", "imp.check", "pytest -q")
      git_run (repo, "config", "--add", "imp.check", "ruff check")

      assert config.get_all ("check") == [ "pytest -q", "ruff check" ]


class TestIdentity:

   def test_actor_uses_native_agent_session (self, monkeypatch):
      monkeypatch.setattr (identity.config, "get", lambda _key: "")
      monkeypatch.delenv ("CLAUDE_SESSION_ID", raising=False)
      monkeypatch.setenv ("CODEX_THREAD_ID", "Thread 123")

      assert identity.actor () == "actor:codex:thread-123"
      assert identity.is_agent ()

      monkeypatch.delenv ("CODEX_THREAD_ID")
      monkeypatch.setenv ("CLAUDE_SESSION_ID", "Session 456")

      assert identity.actor () == "actor:claude:session-456"

      monkeypatch.delenv ("CLAUDE_SESSION_ID")
      monkeypatch.setenv ("CLAUDE_CODE_SESSION_ID", "Session 789")

      assert identity.actor () == "actor:claude:session-789"

   def test_the_actor_ignores_the_environment (self, monkeypatch):
      monkeypatch.setenv ("IMP_ACTOR_ID", "actor:human:someone-else")
      monkeypatch.delenv ("CODEX_THREAD_ID", raising=False)
      monkeypatch.delenv ("CLAUDE_SESSION_ID", raising=False)
      monkeypatch.setattr (identity.config, "get", lambda _key: "")

      assert identity.actor ().startswith ("actor:human:")
      assert "someone-else" not in identity.actor ()
      assert not identity.is_agent ()


class TestCommandsRegistered:

   def _help (self, name):
      return CliRunner ().invoke (app, [ name, "--help" ])

   def _options (self, name):
      return { option for param in get_command (app).commands [name].params for option in param.opts }

   def test_start (self):
      result = self._help ("start")
      assert result.exit_code == 0
      assert "--repo" in self._options ("start")
      assert "--ticket" in self._options ("start")

   def test_commit (self):
      result = self._help ("commit")
      assert result.exit_code == 0

   def test_review (self):
      result = self._help ("review")
      assert result.exit_code == 0
      assert "--ask" in self._options ("review")

   def test_cleanup (self):
      result = self._help ("cleanup")
      assert result.exit_code == 0
      assert "--keep" in self._options ("cleanup")

   def test_undo (self):
      result = self._help ("undo")
      assert result.exit_code == 0

   def test_worktree (self):
      result = self._help ("worktree")
      assert result.exit_code == 0

   def test_doctor_has_no_agent_adapter_options (self):
      result = self._help ("doctor")
      assert result.exit_code == 0
      assert "--agents" not in self._options ("doctor")
