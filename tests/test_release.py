from imp import git
from tests.conftest import commit_file, git_run


class TestReleaseIntegration:

   def test_tag_after_commit (self, repo):
      commit_file (repo, "file.txt", "release content\n", "feat: add feature")

      git.tag ("v1.0.0")
      assert git.tag_exists ("v1.0.0")
      assert git.last_tag () == "v1.0.0"

   def test_squash_to_tag (self, repo):
      git_run (repo, "tag", "v0.1.0")

      for i in range (3):
         commit_file (repo, "file.txt", f"change {i}\n", f"feat: change {i}")

      assert git.commit_count () == 4

      git.reset ("v0.1.0", soft=True)
      git.stage ()
      git.commit ("chore: release v0.2.0")

      assert git.commit_count () == 2

      git.tag ("v0.2.0")
      assert git.tag_exists ("v0.2.0")

   def test_rollback_tag (self, repo):
      git.tag ("v9.9.9")
      assert git.tag_exists ("v9.9.9")
      git.tag_delete ("v9.9.9")
      assert not git.tag_exists ("v9.9.9")
