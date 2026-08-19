import sys
from pathlib import Path

import pytest

from imp_git import features, git, integration, state
from imp_git.commands import release as release_command
from tests.conftest import commit_file

ACTOR = "actor:human:anders"


def _feature (name: str = "checkout") -> dict:
   feature = features.apply_start (features.plan_start (name, actor_id=ACTOR))
   commit_file (Path (feature ["path"]), f"{name}.txt", f"{name}\n", f"feat: add {name}")
   return features.find (feature ["feature_id"])


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
      assert features.find (feature ["feature_id"]) is None
      assert not Path (feature ["path"]).exists ()

   def test_apply_refuses_a_moved_target (self, repo):
      feature = _feature ()
      plan = integration.plan_done (feature)
      commit_file (repo, "other.txt", "other\n", "chore: move target")

      with pytest.raises (state.StateError, match="target moved"):
         integration.apply_done (plan)

      assert features.find (feature ["feature_id"]) ["state"] == "active"


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
