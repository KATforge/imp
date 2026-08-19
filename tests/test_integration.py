import sys
from pathlib import Path

import pytest

from imp_git import features, git, integration, source_release, state
from tests.conftest import commit_file, git_run

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


class TestSourceRelease:

   def test_release_uses_the_checked_out_branch (self, repo_with_origin, monkeypatch):
      git_run (repo_with_origin, "checkout", "-b", "develop", "master")
      git_run (repo_with_origin, "push", "-u", "origin", "develop")
      commit_file (repo_with_origin, "develop.txt", "develop\n", "feat: advance develop")
      monkeypatch.setattr (source_release.gh, "available", lambda: False)

      plan = source_release.plan_release ()

      assert plan ["payload"] ["target_ref"] == "develop"
      assert { commit ["subject"] for commit in plan ["payload"] ["push_commits"] } == {
         "feat: advance develop",
         "chore: release v0.0.1",
      }

   def test_interrupted_release_resumes_from_its_tag (self, repo, monkeypatch):
      monkeypatch.setattr (source_release.gh, "available", lambda: False)
      monkeypatch.setattr (source_release.git, "remote_exists", lambda: False)
      first = source_release.plan_release ()
      payload = first ["payload"]
      git.tag (str (payload ["tag"]), str (payload ["commit_oid"]))

      second = source_release.plan_release ()

      assert second ["payload"] ["resumed"] is True
      assert second ["payload"] ["commit_oid"] == payload ["commit_oid"]

   def test_github_failure_is_not_success (self, repo, monkeypatch):
      plan = source_release.plan_release ()
      plan ["payload"] ["github_release"] = True
      monkeypatch.setattr (source_release.gh, "release_view", lambda _tag: {})
      monkeypatch.setattr (source_release.gh, "release_create", lambda *_args, **_kwargs: False)

      with pytest.raises (state.StateError, match="GitHub release creation failed"):
         source_release.apply_release (plan)

   def test_local_release_moves_branch_and_tag (self, repo):
      plan = source_release.plan_release (local=True)

      receipt = source_release.apply_release (plan)

      assert receipt ["tag"] == "v0.0.1"
      assert git.rev_parse ("v0.0.1") == git.rev_parse ("main")
