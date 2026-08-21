from pathlib import Path

import pytest
import typer

from imp_git import features, git, integration, layers, state
from imp_git.commands import undo as undo_cmd
from tests.conftest import commit_file, git_run


def _integrated (name: str = "checkout") -> dict:
   feature = features.apply_start (features.plan_start (name))
   commit_file (Path (feature ["path"]), f"{name}.txt", f"{name}\n", f"feat: add {name}")
   integration.apply_merge (integration.plan_merge (features.find (name)))
   return feature


class TestUndo:

   def test_undo_restores_trunk_and_the_feature (self, repo):
      before = git.rev_parse ("main")
      _integrated ()
      layer = git.rev_parse ("main")

      receipt = undo_cmd.undo ()

      assert git.rev_parse ("main") == before
      assert not (repo / "checkout.txt").exists ()
      assert git.rev_parse ("feature/checkout") == layer
      assert features.find ("checkout") ["worktree_state"] == "live"
      assert receipt ["branch"] == "feature/checkout"

   def test_undone_work_can_be_reintegrated (self, repo):
      _integrated ()
      undo_cmd.undo ()

      integration.apply_merge (integration.plan_merge (features.find ("checkout")))

      assert git.capture ("show", "main:checkout.txt").strip () == "checkout"

   def test_undo_refuses_a_named_mismatch (self, repo):
      _integrated ("checkout")

      with pytest.raises (typer.Exit):
         undo_cmd.undo ("other")

   def test_undo_refuses_when_trunk_moved_after (self, repo):
      _integrated ()
      commit_file (repo, "later.txt", "later\n", "chore: land later work")

      with pytest.raises (typer.Exit):
         undo_cmd.undo ()

   def test_undo_refuses_a_pushed_layer (self, repo_with_origin):
      git_run (repo_with_origin, "checkout", "master")
      _integrated ()
      git_run (repo_with_origin, "push", "origin", "master")

      with pytest.raises (typer.Exit):
         undo_cmd.undo ()

   def test_undo_without_layers_fails_cleanly (self, repo):
      with pytest.raises (typer.Exit):
         undo_cmd.undo ()

   def test_undo_refuses_a_trunk_dirtied_after_planning (self, repo):
      _integrated ()
      plan = undo_cmd._plan ("main", "")
      (repo / "file.txt").write_text ("meddled\n")

      with pytest.raises (state.StateError, match="dirty"):
         undo_cmd._apply (plan)

      assert (repo / "file.txt").read_text () == "meddled\n"
      assert not git.ref_exists ("feature/checkout")

   def test_merge_into_targets_another_branch (self, repo):
      git_run (repo, "branch", "develop")
      feature = features.apply_start (features.plan_start ("sidework"))
      commit_file (Path (feature ["path"]), "side.txt", "side\n", "feat: add side work")
      trunk_before = git.rev_parse ("main")

      from imp_git.commands import merge as merge_cmd
      merge_cmd.merge ("sidework", into="develop")

      assert git.rev_parse ("main") == trunk_before
      assert git.capture ("show", "develop:side.txt").strip () == "side"

   def test_done_remains_an_alias (self, repo):
      from typer.testing import CliRunner

      from imp_git.main import app

      feature = features.apply_start (features.plan_start ("aliased"))
      commit_file (Path (feature ["path"]), "aliased.txt", "aliased\n", "feat: add aliased work")
      result = CliRunner ().invoke (app, [ "--json", "--yes", "done", "aliased" ])

      assert result.exit_code == 0
      assert '"imp.merge.v1"' in result.output
      assert git.capture ("show", "main:aliased.txt").strip () == "aliased"

   def test_undo_applies_nothing_when_trunk_moved_after_planning (self, repo):
      _integrated ()
      plan = undo_cmd._plan ("main", "")
      commit_file (repo, "later.txt", "later\n", "chore: land later work")
      moved = git.rev_parse ("main")

      with pytest.raises (state.StateError):
         undo_cmd._apply (plan)

      assert git.rev_parse ("main") == moved
      assert not git.ref_exists ("feature/checkout")
      assert len (layers.all ()) == 1
