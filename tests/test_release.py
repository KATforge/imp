import subprocess

from imp import git, version


class TestReleaseIntegration:

   def test_tag_after_commit (self, repo):
      (repo / "file.txt").write_text ("release content\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
      subprocess.run (
         [ "git", "commit", "-m", "feat: add feature" ],
         cwd=repo, check=True, capture_output=True,
      )

      git.tag ("v1.0.0")
      assert git.tag_exists ("v1.0.0")
      assert git.last_tag () == "v1.0.0"

   def test_changelog_generation (self):
      subjects = "feat: add login\nfix: resolve crash\nchore: update deps"
      result = version.changelog_from_commits (subjects)
      assert "### Added" in result
      assert "Add login" in result
      assert "### Fixed" in result
      assert "Resolve crash" in result
      assert "### Changed" in result
      assert "Update deps" in result

   def test_squash_to_tag (self, repo):
      subprocess.run ([ "git", "tag", "v0.1.0" ], cwd=repo, check=True)

      for i in range (3):
         (repo / "file.txt").write_text (f"change {i}\n")
         subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
         subprocess.run (
            [ "git", "commit", "-m", f"feat: change {i}" ],
            cwd=repo, check=True, capture_output=True,
         )

      assert git.commit_count () == 4

      git.reset ("v0.1.0", soft=True)
      git.stage (all=True)
      git.commit ("chore: release v0.2.0")

      assert git.commit_count () == 2

      git.tag ("v0.2.0")
      assert git.tag_exists ("v0.2.0")

   def test_changelog_file_creation (self, repo):
      changelog = repo / "CHANGELOG.md"
      assert not changelog.exists ()

      changelog.write_text (
         "# Changelog\n\n"
         "All notable changes to this project will be documented in this file.\n\n"
         "## [0.1.0] - 2025-01-01\n\n"
         "### Added\n- Initial release\n"
      )

      content = changelog.read_text ()
      assert "## [0.1.0]" in content

   def test_bump_versions (self):
      assert version.bump ("1.0.0", "patch") == "1.0.1"
      assert version.bump ("1.0.0", "minor") == "1.1.0"
      assert version.bump ("1.0.0", "major") == "2.0.0"

   def test_rollback_tag (self, repo):
      git.tag ("v9.9.9")
      assert git.tag_exists ("v9.9.9")
      git.tag_delete ("v9.9.9")
      assert not git.tag_exists ("v9.9.9")
