import json
import os
from pathlib import Path

import pytest
import typer

from imp_git import features, roster, runtime, state, workspace
from tests.conftest import commit_file, git_run


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
   _repo (root, "api")
   _repo (root, "web")
   monkeypatch.chdir (root)
   return root


def _start (repository: Path, name: str):
   from imp_git import repo as repo_mod

   previous = Path.cwd ()
   os.chdir (repository)
   try:
      repo_mod.load.cache_clear ()
      return features.apply_start (features.plan_start (name, actor_id="actor:human:anders"))
   finally:
      os.chdir (previous)
      repo_mod.load.cache_clear ()


class TestRoster:

   def test_open_feature_is_listed (self, demo):
      _start (demo / "api", "checkout")

      entry = roster.collect (workspace.here (str (demo))) [0]

      assert entry ["name"] == "checkout"
      assert entry ["condition"] == "open"
      assert entry ["repositories"] == [ "api" ]

   def test_dirty_feature_is_named_without_guessing_readiness (self, demo):
      feature = _start (demo / "api", "checkout")
      (Path (feature ["path"]) / "loose.txt").write_text ("unsaved\n")

      entry = roster.collect (workspace.here (str (demo))) [0]

      assert entry ["condition"] == "dirty"

   def test_one_name_groups_across_repositories (self, demo):
      for alias in [ "web", "api" ]:
         _start (demo / alias, "checkout")

      entry = roster.collect (workspace.here (str (demo))) [0]

      assert entry ["repositories"] == [ "api", "web" ]
      assert [ member ["alias"] for member in roster.ordered_members (entry) ] == [ "api", "web" ]


class TestDiscovery:

   def test_nested_repositories_need_no_manifest (self, tmp_path, monkeypatch):
      root = tmp_path / "projects"
      root.mkdir ()
      _repo (root, "alpha")
      nested = root / "group"
      nested.mkdir ()
      _repo (nested, "beta")
      monkeypatch.chdir (root)

      assert sorted (workspace.here () ["services"]) == [ "alpha", "group/beta" ]

   def test_ambiguous_suffix_is_refused (self, tmp_path, monkeypatch):
      root = tmp_path / "projects"
      one = root / "one"
      two = root / "two"
      one.mkdir (parents=True)
      two.mkdir ()
      _repo (one, "api")
      _repo (two, "api")
      monkeypatch.chdir (root)

      with pytest.raises (state.StateError, match="Ambiguous repository"):
         workspace.match (workspace.here (), "api")


class TestSpan:

   def _ready (self, demo: Path):
      from imp_git.commands import start as start_cmd

      start_cmd.start (name="checkout", repos=[ "web", "api" ])
      for member in roster.collect (workspace.here (str (demo))) [0] ["members"]:
         commit_file (Path (member ["path"]), "new.txt", "work\n", "feat: work")

   def test_start_records_the_requested_order (self, demo):
      from imp_git.commands import start as start_cmd

      data = start_cmd.start (name="checkout", repos=[ "web", "api" ])

      assert [ member ["alias"] for member in data ["members"] ] == [ "web", "api" ]

   def test_failed_start_unwinds_every_member (self, demo, monkeypatch):
      from imp_git.commands import start as start_cmd

      apply = features.apply_start
      calls = []

      def fail_second (plan):
         calls.append (plan)
         if len (calls) == 2:
            raise state.StateError ("failed")
         return apply (plan)

      monkeypatch.setattr (start_cmd.features, "apply_start", fail_second)

      with pytest.raises (typer.Exit):
         start_cmd.start (name="checkout", repos=[ "api", "web" ])

      assert roster.collect (workspace.here (str (demo))) == []

   def test_done_emits_one_exact_result (self, demo, capsys):
      from imp_git.commands import done as done_cmd

      self._ready (demo)
      runtime.configure (json=True, yes=True)
      capsys.readouterr ()

      done_cmd.done ("checkout")

      value = json.loads (capsys.readouterr ().out)
      assert value ["schema"] == "imp.promote.v3"
      assert value ["data"] ["order"] == [ "web", "api" ]
      assert value ["data"] ["completed"] == [ "web", "api" ]

   def test_done_requires_approval (self, demo, capsys):
      from imp_git.commands import done as done_cmd

      self._ready (demo)
      runtime.configure (json=True, no_input=True)
      capsys.readouterr ()

      with pytest.raises (typer.Exit):
         done_cmd.done ("checkout")

      assert json.loads (capsys.readouterr ().out) ["schema"] == "imp.error.v1"
