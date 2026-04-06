import pytest
import typer

from imp import git
from tests.conftest import commit_file


class TestUndoIntegration:

   def test_soft_reset_preserves_changes (self, repo):
      commit_file (repo, "file.txt", "second\n", "feat: second change")
      assert git.commit_count () == 2

      git.reset ("HEAD~1", soft=True)

      assert git.commit_count () == 1
      staged = git.diff (staged=True)
      assert "second" in staged

   def test_undo_multiple (self, repo):
      for i in range (3):
         commit_file (repo, "file.txt", f"change {i}\n", f"feat: change {i}")

      assert git.commit_count () == 4
      git.reset ("HEAD~3", soft=True)
      assert git.commit_count () == 1

   def test_cannot_undo_past_initial (self, repo):
      assert git.commit_count () == 1
      with pytest.raises (typer.Exit):
         git.reset ("HEAD~2", soft=True)
