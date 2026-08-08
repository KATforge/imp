import json

from typer.main import get_command
from typer.testing import CliRunner

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
      assert "--plan" in self._options ("commit")

   def test_worktree (self):
      result = self._help ("worktree")
      assert result.exit_code == 0
