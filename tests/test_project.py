import json

from typer.main import get_command
from typer.testing import CliRunner

from imp_git import identity
from imp_git import repo as repo_mod
from imp_git.main import app


class TestRepoConfig:

   def test_missing_returns_defaults (self, repo):
      assert repo_mod.load () == {}
      assert repo_mod.get ("commit:max_subject") == 72

   def test_reads_imp (self, repo):
      (repo / ".imp").write_text (json.dumps ({
         "commit:max_subject": 50,
      }))
      repo_mod.load.cache_clear ()

      assert repo_mod.get ("commit:max_subject") == 50

   def test_invalid_json_ignored (self, repo):
      (repo / ".imp").write_text ("{ not json")
      repo_mod.load.cache_clear ()

      assert repo_mod.load () == {}


class TestIdentity:

   def test_actor_uses_native_agent_session (self, monkeypatch):
      monkeypatch.setattr (identity.config, "get", lambda _key: None)
      monkeypatch.delenv ("CLAUDE_SESSION_ID", raising=False)
      monkeypatch.setenv ("CODEX_THREAD_ID", "Thread 123")

      assert identity.actor () == "actor:codex:thread-123"

      monkeypatch.delenv ("CODEX_THREAD_ID")
      monkeypatch.setenv ("CLAUDE_SESSION_ID", "Session 456")

      assert identity.actor () == "actor:claude:session-456"


class TestCommandsRegistered:

   def _help (self, name):
      return CliRunner ().invoke (app, [ name, "--help" ])

   def _options (self, name):
      return { option for param in get_command (app).commands [name].params for option in param.opts }

   def test_start (self):
      result = self._help ("start")
      assert result.exit_code == 0
      assert "--task" in self._options ("start")

   def test_commit (self):
      result = self._help ("commit")
      assert result.exit_code == 0

   def test_worktree (self):
      result = self._help ("worktree")
      assert result.exit_code == 0

   def test_doctor_has_no_agent_adapter_options (self):
      result = self._help ("doctor")
      assert result.exit_code == 0
      assert "--agents" not in self._options ("doctor")


class TestMachineConfiguration:

   def test_the_defaults_file_is_written_on_first_read (self, tmp_path, monkeypatch):
      from imp_git import config

      monkeypatch.setenv ("XDG_CONFIG_HOME", str (tmp_path))
      config.load.cache_clear ()
      target = tmp_path / "imp" / "config.json"

      assert not target.exists ()
      settings = config.load ()

      assert target.is_file ()
      assert json.loads (target.read_text ()) == settings
      assert settings ["provider"] == "claude"
      config.load.cache_clear ()

   def test_an_existing_file_is_never_overwritten (self, tmp_path, monkeypatch):
      from imp_git import config

      monkeypatch.setenv ("XDG_CONFIG_HOME", str (tmp_path))
      target = tmp_path / "imp" / "config.json"
      target.parent.mkdir (parents=True)
      target.write_text (json.dumps ({ "schema": "imp.machine.v1", "provider": "ollama" }))
      config.load.cache_clear ()

      assert config.load () ["provider"] == "ollama"
      assert json.loads (target.read_text ()) ["provider"] == "ollama"
      config.load.cache_clear ()

   def test_a_read_only_home_still_yields_defaults (self, tmp_path, monkeypatch):
      from imp_git import config

      monkeypatch.setenv ("XDG_CONFIG_HOME", str (tmp_path / "nope"))
      monkeypatch.setattr (config.Path, "mkdir", lambda *_a, **_k: (_ for _ in ()).throw (OSError ()))
      config.load.cache_clear ()

      assert config.load () ["provider"] == "claude"
      config.load.cache_clear ()

   def test_machine_configuration_ignores_the_environment (self, tmp_path, monkeypatch):
      from imp_git import config

      monkeypatch.setenv ("XDG_CONFIG_HOME", str (tmp_path))
      monkeypatch.setenv ("IMP_AI_PROVIDER", "ollama")
      monkeypatch.setenv ("IMP_AI_MODEL_FAST", "llama3.2")
      config.load.cache_clear ()

      assert config.load () ["provider"] == "claude"
      assert config.load () ["model:fast"] == "haiku"
      config.load.cache_clear ()

   def test_the_actor_ignores_the_environment (self, monkeypatch):
      from imp_git import identity, runtime

      monkeypatch.setenv ("IMP_ACTOR_ID", "actor:human:someone-else")
      monkeypatch.delenv ("CODEX_THREAD_ID", raising=False)
      monkeypatch.delenv ("CLAUDE_SESSION_ID", raising=False)
      monkeypatch.setattr (identity.config, "get", lambda _key: None)
      runtime.configure ()

      assert identity.actor ().startswith ("actor:human:")
      assert "someone-else" not in identity.actor ()
