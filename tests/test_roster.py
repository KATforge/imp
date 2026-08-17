import os
from pathlib import Path

import pytest

from imp_git import conflicts, features, git, roster, state, workspace
from tests.conftest import commit_file, git_run

MANIFEST = """
schema: katforge.workspace.v1
name: demo
services:
  api:
    path: api
  web:
    path: web
    needs:
      api: "*"
"""


def _repo (root: Path, name: str) -> Path:
   origin = root / f"{name}.git"
   work = root / name
   git_run (root, "init", "--bare", "-b", "master", str (origin))
   git_run (root, "init", "-b", "master", str (work))
   git_run (work, "config", "user.email", "test@test.com")
   git_run (work, "config", "user.name", "Test")
   commit_file (work, "file.txt", "trunk\n", "Initial commit")
   git_run (work, "remote", "add", "origin", str (origin))
   git_run (work, "push", "-u", "origin", "master")

   return work


@pytest.fixture
def demo (tmp_path, monkeypatch):
   root = tmp_path / "workspace"
   root.mkdir ()
   (root / "workspace.yaml").write_text (MANIFEST)
   _repo (root, "api")
   _repo (root, "web")
   monkeypatch.setenv ("XDG_STATE_HOME", str (tmp_path / "state"))
   previous = Path.cwd ()
   os.chdir (root)
   workspace.load.cache_clear ()
   yield root
   os.chdir (previous)
   workspace.load.cache_clear ()


def _start (repository: Path, name: str, path: Path):
   previous = Path.cwd ()
   os.chdir (repository)
   try:
      from imp_git import repo as repo_mod
      repo_mod.load.cache_clear ()
      plan = features.plan_start (name, actor_id="actor:human:anders", path=str (path))
      return features.apply_start (plan)
   finally:
      os.chdir (previous)
      from imp_git import repo as repo_mod
      repo_mod.load.cache_clear ()


class TestRoster:

   def test_an_untouched_feature_reads_as_empty (self, demo, tmp_path):
      _start (demo / "api", "checkout", tmp_path / "wt-api")

      entries = roster.collect (workspace.load (str (demo)))

      assert [ entry ["name"] for entry in entries ] == [ "checkout" ]
      assert entries [0] ["condition"] == roster.EMPTY
      assert entries [0] ["repositories"] == [ "api" ]
      assert roster.promotable (entries) == []

   def test_a_committed_feature_reads_as_ready (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout", tmp_path / "wt-api")
      commit_file (Path (feature ["path"]), "new.txt", "work\n", "feat: work")

      entries = roster.collect (workspace.load (str (demo)))

      assert entries [0] ["condition"] == roster.READY
      assert entries [0] ["members"] [0] ["ahead"] == 1
      assert entries [0] ["members"] [0] ["repository"] == str (demo / "api")
      assert len (roster.promotable (entries)) == 1

   def test_uncommitted_work_reads_as_dirty (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout", tmp_path / "wt-api")
      commit_file (Path (feature ["path"]), "new.txt", "work\n", "feat: work")
      (Path (feature ["path"]) / "loose.txt").write_text ("unsaved\n")

      entries = roster.collect (workspace.load (str (demo)))

      assert entries [0] ["condition"] == roster.DIRTY

   def test_one_name_in_two_repositories_groups_and_orders (self, demo, tmp_path):
      for alias in [ "web", "api" ]:
         feature = _start (demo / alias, "checkout", tmp_path / f"wt-{alias}")
         commit_file (Path (feature ["path"]), "new.txt", "work\n", "feat: work")

      value = workspace.load (str (demo))
      entries = roster.collect (value)

      assert len (entries) == 1
      assert entries [0] ["repositories"] == [ "api", "web" ]
      assert [ member ["alias"] for member in roster.ordered_members (value, entries [0]) ] == [ "api", "web" ]

   def test_the_worst_member_decides_the_grouped_condition (self, demo, tmp_path):
      ready = _start (demo / "api", "checkout", tmp_path / "wt-api")
      commit_file (Path (ready ["path"]), "new.txt", "work\n", "feat: work")
      _start (demo / "web", "checkout", tmp_path / "wt-web")

      entries = roster.collect (workspace.load (str (demo)))

      assert entries [0] ["condition"] == roster.EMPTY


class TestConflictResolution:

   def _diverged (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout", tmp_path / "wt-api")
      commit_file (Path (feature ["path"]), "file.txt", "feature side\n", "feat: change the line")
      commit_file (demo / "api", "file.txt", "trunk side\n", "fix: change the same line")
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         return feature, git.rev_parse ("master"), git.rev_parse (str (feature ["branch"]))
      finally:
         os.chdir (previous)

   def test_ours_keeps_trunk (self, demo, tmp_path):
      _feature, target, source = self._diverged (demo, tmp_path)
      scratch = tmp_path / "scratch"
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         git.worktree_add_detached (str (scratch), target)
         tree, decisions = conflicts.resolve (str (scratch), target, source, choice=conflicts.OURS)

         assert tree
         assert decisions == [ { "choice": "ours", "path": "file.txt" } ]
         assert (scratch / "file.txt").read_text () == "trunk side\n"
      finally:
         os.chdir (previous)

   def test_theirs_takes_the_feature (self, demo, tmp_path):
      _feature, target, source = self._diverged (demo, tmp_path)
      scratch = tmp_path / "scratch"
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         git.worktree_add_detached (str (scratch), target)
         _tree, decisions = conflicts.resolve (str (scratch), target, source, choice=conflicts.THEIRS)

         assert decisions [0] ["choice"] == "theirs"
         assert (scratch / "file.txt").read_text () == "feature side\n"
      finally:
         os.chdir (previous)

   def test_a_clean_merge_records_no_decisions (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout", tmp_path / "wt-api")
      commit_file (Path (feature ["path"]), "only-here.txt", "work\n", "feat: work")
      scratch = tmp_path / "scratch"
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         target = git.rev_parse ("master")
         source = git.rev_parse (str (feature ["branch"]))
         git.worktree_add_detached (str (scratch), target)
         tree, decisions = conflicts.resolve (str (scratch), target, source)

         assert tree
         assert decisions == []
      finally:
         os.chdir (previous)

   def test_an_editor_that_leaves_markers_is_refused (self, demo, tmp_path, monkeypatch):
      _feature, target, source = self._diverged (demo, tmp_path)
      scratch = tmp_path / "scratch"
      monkeypatch.setenv ("IMP_EDITOR", "true")
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         git.worktree_add_detached (str (scratch), target)

         with pytest.raises (state.StateError, match="Conflict markers remain"):
            conflicts.resolve (str (scratch), target, source, choice=conflicts.EDIT)
      finally:
         os.chdir (previous)

   def test_a_deletion_beats_a_stale_edit_by_default (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout", tmp_path / "wt-api")
      commit_file (Path (feature ["path"]), "file.txt", "edited\n", "feat: edit the file")
      git_run (demo / "api", "rm", "file.txt")
      git_run (demo / "api", "commit", "-m", "chore: drop the file")
      scratch = tmp_path / "scratch"
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         target = git.rev_parse ("master")
         source = git.rev_parse (str (feature ["branch"]))
         git.worktree_add_detached (str (scratch), target)
         _tree, decisions = conflicts.resolve (str (scratch), target, source, choice=conflicts.RESOLVE)

         assert decisions == [ { "choice": "deleted", "path": "file.txt" } ]
         assert not (scratch / "file.txt").exists ()
      finally:
         os.chdir (previous)

   def test_theirs_restores_a_file_trunk_deleted (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout", tmp_path / "wt-api")
      commit_file (Path (feature ["path"]), "file.txt", "edited\n", "feat: edit the file")
      git_run (demo / "api", "rm", "file.txt")
      git_run (demo / "api", "commit", "-m", "chore: drop the file")
      scratch = tmp_path / "scratch"
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         target = git.rev_parse ("master")
         source = git.rev_parse (str (feature ["branch"]))
         git.worktree_add_detached (str (scratch), target)
         conflicts.resolve (str (scratch), target, source, choice=conflicts.THEIRS)

         assert (scratch / "file.txt").read_text () == "edited\n"
      finally:
         os.chdir (previous)
