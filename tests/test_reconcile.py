import os
import subprocess
from pathlib import Path

import pytest

from imp_git import console, git, workflow
from imp_git.commands import push as push_cmd
from imp_git.commands import resolve as resolve_cmd
from tests.conftest import commit_file, git_run


def _diverged (tmp_path, ours: dict [str, str], theirs: dict [str, str]) -> Path:
   """Build a clone one commit ahead of and one commit behind origin/main.

   ours/theirs map filename to content: the same key in both makes the rebase
   conflict, distinct keys make it clean. Leaves cwd inside the clone.
   """

   origin = tmp_path / "origin.git"
   work = tmp_path / "work"
   other = tmp_path / "other"

   git_run (tmp_path, "init", "--bare", "-b", "main", str (origin))

   git_run (tmp_path, "init", "-b", "main", str (work))
   git_run (work, "config", "user.email", "test@test.com")
   git_run (work, "config", "user.name", "Test")
   commit_file (work, "file.txt", "base\n", "Initial commit")
   git_run (work, "remote", "add", "origin", str (origin))
   git_run (work, "push", "-u", "origin", "main")

   git_run (tmp_path, "clone", str (origin), str (other))
   git_run (other, "config", "user.email", "test@test.com")
   git_run (other, "config", "user.name", "Test")

   for name, content in theirs.items ():
      commit_file (other, name, content, f"feat: upstream {name}")

   git_run (other, "push", "origin", "main")

   for name, content in ours.items ():
      commit_file (work, name, content, f"feat: local {name}")

   os.chdir (work)

   return work


@pytest.fixture
def diverged (tmp_path):
   old_cwd = Path.cwd ()
   yield lambda ours, theirs: _diverged (tmp_path, ours, theirs)
   os.chdir (old_cwd)


class TestMergePreview:
   """Dry-run conflict detection: names the damage without touching the tree."""

   def test_clean_integration_is_empty (self, diverged):
      diverged ({ "ours.txt": "ours\n" }, { "theirs.txt": "theirs\n" })
      git.fetch ()

      assert git.merge_preview ("@{u}") == []

   def test_names_conflicting_files (self, diverged):
      diverged ({ "file.txt": "ours\n" }, { "file.txt": "theirs\n" })
      git.fetch ()

      assert git.merge_preview ("@{u}") == [ "file.txt" ]

   def test_leaves_worktree_and_index_untouched (self, diverged):
      work = diverged ({ "file.txt": "ours\n" }, { "file.txt": "theirs\n" })
      git.fetch ()

      git.merge_preview ("@{u}")

      assert (work / "file.txt").read_text () == "ours\n"
      assert git.conflicts () == []
      assert git.is_clean ()


class TestReconcile:
   """A publish must never leave the branch diverged (KAT: ship pushed without
   pulling, origin had moved, the rejected push left 2-ahead/1-behind)."""

   def test_rebases_clean_divergence (self, diverged):
      work = diverged ({ "ours.txt": "ours\n" }, { "theirs.txt": "theirs\n" })

      assert workflow.reconcile () is True
      assert git.count_behind () == 0
      assert git.count_ahead () == 1
      assert (work / "theirs.txt").is_file ()

   def test_up_to_date_is_a_noop (self, diverged):
      diverged ({}, {})

      assert workflow.reconcile () is True
      assert git.count_ahead () == 0

   def test_conflicts_offer_automatic_reconcile (self, diverged, monkeypatch):
      diverged ({ "file.txt": "ours\n" }, { "file.txt": "theirs\n" })

      asked = []
      monkeypatch.setattr (console, "choose", lambda title, options: asked.append (options) or options [0])

      calls = []
      monkeypatch.setattr (workflow, "integrate", lambda ref, **kw: calls.append ((ref, kw)) or True)

      assert workflow.reconcile () is True
      assert asked == [ [ "Reconcile automatically", "Leave it" ] ]
      assert calls == [ ("@{u}", { "strategy": "rebase", "auto": True }) ]

   def test_declining_conflicts_blocks_the_push (self, diverged, monkeypatch):
      monkeypatch.setattr (console, "choose", lambda title, options: "Leave it")
      diverged ({ "file.txt": "ours\n" }, { "file.txt": "theirs\n" })

      assert workflow.reconcile () is False
      assert git.count_ahead () == 1
      assert git.count_behind () == 1

   def test_refuses_a_dirty_worktree (self, diverged):
      work = diverged ({ "ours.txt": "ours\n" }, { "theirs.txt": "theirs\n" })
      (work / "ours.txt").write_text ("edited\n")

      assert workflow.reconcile () is False
      assert git.count_behind () == 1


class TestAutomaticResolution:

   def test_does_not_stage_ai_output_with_conflict_markers (self, repo, monkeypatch):
      conflict = "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> main\n"
      (repo / "file.txt").write_text (conflict)

      monkeypatch.setattr (resolve_cmd.ai, "smart", lambda prompt: conflict)
      monkeypatch.setattr (resolve_cmd.git, "conflicts", lambda: [ "file.txt" ])
      monkeypatch.setattr (resolve_cmd.git, "merge_in_progress", lambda: False)
      monkeypatch.setattr (resolve_cmd.git, "rebase_in_progress", lambda: False)

      staged = []
      monkeypatch.setattr (resolve_cmd.git, "add", lambda paths: staged.extend (paths))

      resolve_cmd.resolve (yes=True, whisper="", favor_ours=False, favor_theirs=False)

      assert staged == []
      assert (repo / "file.txt").read_text () == conflict

class TestPushReconciles:

   def test_push_rebases_then_lands (self, diverged):
      diverged ({ "ours.txt": "ours\n" }, { "theirs.txt": "theirs\n" })

      push_cmd.do_push ()

      assert git.count_ahead () == 0
      assert git.count_behind () == 0

   def test_no_pull_still_hits_the_wall (self, diverged):
      diverged ({ "ours.txt": "ours\n" }, { "theirs.txt": "theirs\n" })

      with pytest.raises (subprocess.CalledProcessError):
         push_cmd.do_push (pull=False)

      assert git.count_behind () == 1
