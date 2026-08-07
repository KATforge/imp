import subprocess

import pytest
import typer

from imp_git import git
from imp_git.commands import release as release_cmd
from tests.conftest import commit_file, git_run


class TestReleaseIntegration:

   def test_rejects_attributed_notes_before_mutation (self, repo):
      original = git.rev_parse ("HEAD")

      with pytest.raises (typer.Exit):
         release_cmd.do_release (
            "1.0.0",
            "",
            1,
            will_push=False,
            entry="Generated with Claude Code",
         )

      assert git.rev_parse ("HEAD") == original
      assert not (repo / "CHANGELOG.md").exists ()

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

   def test_rc_rolls_back_when_branch_push_fails (self, repo, monkeypatch):
      package = repo / "package.json"
      package.write_text ('{ "name": "demo", "version": "1.0.0" }\n')
      git.add ([ str (package) ])
      git.commit ("chore: add manifest")
      original = git.rev_parse ("HEAD")

      error = subprocess.CalledProcessError (1, [ "git", "push" ], stderr="offline")
      monkeypatch.setattr (release_cmd, "_push_commits", lambda: (_ for _ in ()).throw (error))

      with pytest.raises (typer.Exit):
         release_cmd._publish_rc (
            "1.0.1-rc.1",
            "notes",
            publish_branch=True,
            will_push=True,
         )

      assert git.rev_parse ("HEAD") == original
      assert not git.tag_exists ("v1.0.1-rc.1")
      assert '"version": "1.0.0"' in package.read_text ()

   def test_rc_keeps_pushed_commit_when_tag_push_fails (self, repo, monkeypatch):
      package = repo / "package.json"
      package.write_text ('{ "name": "demo", "version": "1.0.0" }\n')
      git.add ([ str (package) ])
      git.commit ("chore: add manifest")
      original = git.rev_parse ("HEAD")

      monkeypatch.setattr (release_cmd, "_push_commits", lambda: None)
      error = subprocess.CalledProcessError (1, [ "git", "push" ], stderr="rejected")
      monkeypatch.setattr (release_cmd, "_push_tag", lambda *args, **kwargs: (_ for _ in ()).throw (error))

      with pytest.raises (typer.Exit):
         release_cmd._publish_rc (
            "1.0.1-rc.1",
            "notes",
            publish_branch=True,
            will_push=True,
         )

      assert git.rev_parse ("HEAD") != original
      assert git.tag_exists ("v1.0.1-rc.1")
      assert '"version": "1.0.1-rc.1"' in package.read_text ()
