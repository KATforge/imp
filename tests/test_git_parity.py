from typer.testing import CliRunner

from imp_git import git
from imp_git import main as main_mod
from imp_git.main import app
from tests.conftest import commit_file

runner = CliRunner ()


class TestGitFallback:

   def test_unknown_command_passes_every_argument_to_git (self, monkeypatch):
      seen = []
      monkeypatch.setattr (main_mod.passthrough, "run", lambda args: seen.append (args) or 0)

      result = runner.invoke (app, [ "rev-parse", "--show-toplevel" ])

      assert result.exit_code == 0
      assert seen == [ [ "rev-parse", "--show-toplevel" ] ]

   def test_native_syntax_error_does_not_fall_back_to_git (self, monkeypatch):
      seen = []
      monkeypatch.setattr (main_mod.sys, "argv", [ "imp", "status", "--short" ])
      monkeypatch.setattr (main_mod.passthrough, "run", lambda args: seen.append (args) or 0)

      assert main_mod.run () == 2
      assert seen == []

   def test_git_global_options_fall_back (self, monkeypatch):
      seen = []
      monkeypatch.setattr (main_mod.sys, "argv", [ "imp", "--no-pager", "log", "-1" ])
      monkeypatch.setattr (main_mod.passthrough, "run", lambda args: seen.append (args) or 0)

      assert main_mod.run () == 0
      assert seen == [ [ "--no-pager", "log", "-1" ] ]

   def test_git_diff_raw_flag_falls_back (self, monkeypatch):
      seen = []
      monkeypatch.setattr (main_mod.sys, "argv", [ "imp", "diff", "--raw" ])
      monkeypatch.setattr (main_mod.passthrough, "run", lambda args: seen.append (args) or 0)

      assert main_mod.run () == 0
      assert seen == [ [ "diff", "--raw" ] ]


class TestAdd:

   def test_stages_explicit_paths (self, repo):
      (repo / "file.txt").write_text ("changed\n")

      result = runner.invoke (app, [ "add", "file.txt" ])

      assert result.exit_code == 0
      assert git.staged_files () == [ "file.txt" ]

   def test_add_without_paths_is_plain_git (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      (repo / "new.txt").write_text ("new\n")

      result = runner.invoke (app, [ "add" ])

      assert result.exit_code == 0
      assert git.staged_files () == []


class TestInspection:

   def test_show_displays_commit (self, repo, capfd):
      result = runner.invoke (app, [ "show", "HEAD", "--name-only" ])

      assert result.exit_code == 0
      output = capfd.readouterr ().out
      assert "Initial commit" in output
      assert "file.txt" in output

   def test_history_is_forwarded_unchanged (self, monkeypatch):
      seen = []
      monkeypatch.setattr (main_mod.passthrough, "run", lambda args: seen.append (args) or 9)
      result = runner.invoke (app, [ "history", "file.txt" ])

      assert result.exit_code == 9
      assert seen == [ [ "history", "file.txt" ] ]

   def test_grep_searches_tracked_content (self, repo, capfd):
      result = runner.invoke (app, [ "grep", "hello" ])

      assert result.exit_code == 0
      assert "file.txt:hello" in capfd.readouterr ().out


class TestMutation:

   def test_cherry_pick_applies_commit (self, repo):
      commit_file (repo, "picked.txt", "picked\n", "feat: add picked file")
      ref = git.rev_parse ("HEAD")
      git.reset ("HEAD~1", hard=True)

      result = runner.invoke (app, [ "cherry-pick", ref ])

      assert result.exit_code == 0
      assert (repo / "picked.txt").read_text () == "picked\n"

   def test_restore_is_plain_git (self, repo):
      (repo / "file.txt").write_text ("changed\n")

      result = runner.invoke (app, [ "restore", "file.txt" ])

      assert result.exit_code == 0
      assert (repo / "file.txt").read_text () == "hello\n"
