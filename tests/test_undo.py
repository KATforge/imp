import subprocess

import pytest

from imp import git


class TestUndoIntegration:

   def test_soft_reset_preserves_changes (self, repo):
      (repo / "file.txt").write_text ("second\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
      subprocess.run (
         [ "git", "commit", "-m", "feat: second change" ],
         cwd=repo, check=True, capture_output=True,
      )
      assert git.commit_count () == 2

      git.reset ("HEAD~1", soft=True)

      assert git.commit_count () == 1
      staged = git.diff (staged=True)
      assert "second" in staged

   def test_undo_multiple (self, repo):
      for i in range (3):
         (repo / "file.txt").write_text (f"change {i}\n")
         subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
         subprocess.run (
            [ "git", "commit", "-m", f"feat: change {i}" ],
            cwd=repo, check=True, capture_output=True,
         )

      assert git.commit_count () == 4
      git.reset ("HEAD~3", soft=True)
      assert git.commit_count () == 1

   def test_cannot_undo_past_initial (self, repo):
      assert git.commit_count () == 1
      with pytest.raises (subprocess.CalledProcessError):
         git._run ("reset", "--soft", "HEAD~2")
