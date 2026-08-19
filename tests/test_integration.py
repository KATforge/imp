import sys
from pathlib import Path

import pytest
import typer

from imp_git import features, git, integration, state
from imp_git.commands import done as done_command
from imp_git.commands import release as release_command
from tests.conftest import commit_file, git_run


def _feature (name: str = "checkout") -> dict:
   feature = features.apply_start (features.plan_start (name))
   commit_file (Path (feature ["path"]), f"{name}.txt", f"{name}\n", f"feat: add {name}")
   return features.find (name)


class TestIntegration:

   def test_failed_checks_change_nothing (self, repo, monkeypatch):
      feature = _feature ()
      target_oid = git.rev_parse ("main")
      monkeypatch.setattr (
         integration,
         "_checks",
         lambda: [ { "name": "tests", "run": [ sys.executable, "-c", "raise SystemExit(1)" ] } ],
      )

      plan = integration.plan_done (feature)

      assert plan ["blockers"] == [ "Check failed: tests" ]
      assert git.rev_parse ("main") == target_oid

   def test_done_shows_and_integrates_the_exact_diff (self, repo):
      feature = _feature ()
      plan = integration.plan_done (feature)

      assert "+checkout" in plan ["payload"] ["diff"]

      receipt = integration.apply_done (plan)

      assert receipt ["candidate_oid"] == git.rev_parse ("main")
      assert git.capture ("show", "main:checkout.txt").strip () == "checkout"
      assert features.find ("checkout") is None
      assert not Path (feature ["path"]).exists ()

   def test_done_stamps_the_trunk_reflog (self, repo):
      feature = _feature ()

      integration.apply_done (integration.plan_done (feature))

      entries = git.reflog_entries ("refs/heads/main")
      assert entries [0] ["subject"] == "imp done: feature/checkout"

   def test_apply_refuses_a_moved_target (self, repo):
      feature = _feature ()
      plan = integration.plan_done (feature)
      commit_file (repo, "other.txt", "other\n", "chore: move target")

      with pytest.raises (state.StateError, match="target moved"):
         integration.apply_done (plan)

      assert features.find ("checkout") is not None

   def test_configured_checks_come_from_git_config (self, repo):
      git_run (repo, "config", "--add", "imp.check", "pytest -q")

      assert integration.configured_checks () == [ { "name": "pytest -q", "run": [ "pytest", "-q" ] } ]

      git_run (repo, "config", "--replace-all", "imp.check", "none")

      assert integration.configured_checks () == []

   def test_checks_are_detected_from_the_project (self, repo):
      (repo / "package.json").write_text ('{"scripts": {"test": "node test.js"}}')

      assert integration.configured_checks () == [ { "name": "npm test", "run": [ "npm", "test" ] } ]

   def test_done_all_integrates_every_feature_in_order (self, repo):
      _feature ("first")
      _feature ("second")

      receipt = done_command.done (all_features=True)

      assert receipt ["completed"] == [ "first", "second" ]
      assert git.capture ("show", "main:first.txt").strip () == "first"
      assert git.capture ("show", "main:second.txt").strip () == "second"
      assert features.find ("first") is None
      assert features.find ("second") is None

   def test_done_all_changes_nothing_when_one_feature_is_dirty (self, repo):
      _feature ("first")
      second = _feature ("second")
      target = git.rev_parse ("main")
      (Path (second ["path"]) / "loose.txt").write_text ("dirty\n")

      with pytest.raises (typer.Exit):
         done_command.done (all_features=True)

      assert git.rev_parse ("main") == target
      assert features.find ("first")
      assert features.find ("second")


class TestRelease:

   def test_local_release_tags_the_current_commit (self, repo):
      plan = release_command.plan_release ("1.2.3", local=True)

      receipt = release_command.apply_release (plan)

      assert receipt ["tag"] == "v1.2.3"
      assert git.rev_parse ("v1.2.3") == git.rev_parse ("main")

   def test_release_notes_are_commit_subjects (self, repo):
      commit_file (repo, "change.txt", "change\n", "feat: add release change")

      plan = release_command.plan_release ("1.2.3", local=True)

      assert "- feat: add release change" in plan ["payload"] ["notes"]

   def test_release_pushes_and_publishes (self, repo_with_origin, monkeypatch):
      pushed = []
      monkeypatch.setattr (release_command.gh, "available", lambda: True)
      monkeypatch.setattr (
         release_command.gh, "release_create",
         lambda tag, notes, prerelease: f"https://example.test/{tag}",
      )
      monkeypatch.setattr (release_command.git, "push", lambda **kwargs: pushed.append (kwargs))

      plan = release_command.plan_release ("1.2.3")
      receipt = release_command.apply_release (plan)

      assert pushed == [ { "ref": plan ["payload"] ["branch"] }, { "ref": "v1.2.3" } ]
      assert receipt ["url"] == "https://example.test/v1.2.3"

   def test_release_refuses_an_existing_tag (self, repo):
      git.tag ("v1.2.3")

      with pytest.raises (state.StateError, match="already exists"):
         release_command.plan_release ("1.2.3", local=True)

   def test_release_increments_semver (self, repo):
      git.tag ("v1.2.3")

      assert release_command.plan_release (local=True) ["payload"] ["tag"] == "v1.2.4"
      assert release_command.plan_release (bump="major", local=True) ["payload"] ["tag"] == "v2.0.0"
      assert release_command.plan_release (bump="minor", local=True) ["payload"] ["tag"] == "v1.3.0"
      assert release_command.plan_release (bump="patch", local=True) ["payload"] ["tag"] == "v1.2.4"

   def test_release_advances_and_stabilizes_candidates (self, repo):
      git.tag ("v1.2.3")
      git.tag ("v1.2.4-rc.1")

      assert release_command.plan_release (bump="rc", local=True) ["payload"] ["tag"] == "v1.2.4-rc.2"
      assert release_command.plan_release (bump="stable", local=True) ["payload"] ["tag"] == "v1.2.4"
