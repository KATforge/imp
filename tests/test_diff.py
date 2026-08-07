from typer.testing import CliRunner

from imp_git import git
from imp_git.main import app

runner = CliRunner ()


class TestDiffPassthrough:

   def test_shows_plain_git_diff (self, repo, capfd):
      (repo / "file.txt").write_text ("changed\n")

      result = runner.invoke (app, [ "diff" ])

      assert result.exit_code == 0
      output = capfd.readouterr ().out
      assert "-hello" in output
      assert "+changed" in output
      assert "AI summary" not in output

   def test_supports_git_staged_name_only (self, repo, capfd):
      (repo / "file.txt").write_text ("changed\n")
      git.stage ()

      result = runner.invoke (app, [ "diff", "--staged", "--name-only" ])

      assert result.exit_code == 0
      assert capfd.readouterr ().out.strip () == "file.txt"

   def test_accepts_git_pathspec (self, repo, capfd):
      (repo / "file.txt").write_text ("changed\n")
      (repo / "other.txt").write_text ("other\n")

      result = runner.invoke (app, [ "diff", "--", "file.txt" ])

      assert result.exit_code == 0
      output = capfd.readouterr ().out
      assert "file.txt" in output
      assert "other.txt" not in output

   def test_plain_git_diff_excludes_untracked_files (self, repo, capfd):
      (repo / "new.txt").write_text ("brand new\n")

      result = runner.invoke (app, [ "diff" ])

      assert result.exit_code == 0
      assert "brand new" not in capfd.readouterr ().out
