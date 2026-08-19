from pathlib import Path

import pytest
import typer

from imp_git import features, git, integration
from imp_git.commands import undo as undo_cmd
from tests.conftest import commit_file, git_run


def _integrated (name: str = "checkout") -> dict:
   feature = features.apply_start (features.plan_start (name))
   commit_file (Path (feature ["path"]), f"{name}.txt", f"{name}\n", f"feat: add {name}")
   integration.apply_done (integration.plan_done (features.find (name)))
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

      integration.apply_done (integration.plan_done (features.find ("checkout")))

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
