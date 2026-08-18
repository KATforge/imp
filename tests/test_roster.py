import json
import os
from pathlib import Path

import pytest
import typer

from imp_git import conflicts, features, git, roster, runtime, state, workspace
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
   previous = Path.cwd ()
   os.chdir (root)
   yield root
   os.chdir (previous)


def _start (repository: Path, name: str):
   previous = Path.cwd ()
   os.chdir (repository)
   try:
      from imp_git import repo as repo_mod
      repo_mod.load.cache_clear ()
      plan = features.plan_start (name, actor_id="actor:human:anders")
      return features.apply_start (plan)
   finally:
      os.chdir (previous)
      from imp_git import repo as repo_mod
      repo_mod.load.cache_clear ()


class TestRoster:

   def test_an_untouched_feature_reads_as_empty (self, demo, tmp_path):
      _start (demo / "api", "checkout")

      entries = roster.collect (workspace.here (str (demo)))

      assert [ entry ["name"] for entry in entries ] == [ "checkout" ]
      assert entries [0] ["condition"] == roster.EMPTY
      assert entries [0] ["repositories"] == [ "api" ]
      assert roster.promotable (entries) == []

   def test_a_committed_feature_reads_as_ready (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout")
      commit_file (Path (feature ["path"]), "new.txt", "work\n", "feat: work")

      entries = roster.collect (workspace.here (str (demo)))

      assert entries [0] ["condition"] == roster.READY
      assert entries [0] ["members"] [0] ["ahead"] == 1
      assert entries [0] ["members"] [0] ["repository"] == str (demo / "api")
      assert len (roster.promotable (entries)) == 1

   def test_uncommitted_work_reads_as_dirty (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout")
      commit_file (Path (feature ["path"]), "new.txt", "work\n", "feat: work")
      (Path (feature ["path"]) / "loose.txt").write_text ("unsaved\n")

      entries = roster.collect (workspace.here (str (demo)))

      assert entries [0] ["condition"] == roster.DIRTY

   def test_one_name_in_two_repositories_groups_and_orders (self, demo, tmp_path):
      for alias in [ "web", "api" ]:
         feature = _start (demo / alias, "checkout")
         commit_file (Path (feature ["path"]), "new.txt", "work\n", "feat: work")

      entries = roster.collect (workspace.here (str (demo)))

      assert len (entries) == 1
      assert entries [0] ["repositories"] == [ "api", "web" ]
      assert [ member ["alias"] for member in roster.ordered_members (entries [0]) ] == [ "api", "web" ]

   def test_the_worst_member_decides_the_grouped_condition (self, demo, tmp_path):
      ready = _start (demo / "api", "checkout")
      commit_file (Path (ready ["path"]), "new.txt", "work\n", "feat: work")
      _start (demo / "web", "checkout")

      entries = roster.collect (workspace.here (str (demo)))

      assert entries [0] ["condition"] == roster.EMPTY


class TestConflictResolution:

   def _diverged (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout")
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
      feature = _start (demo / "api", "checkout")
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
      monkeypatch.setenv ("EDITOR", "true")
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         git.worktree_add_detached (str (scratch), target)

         with pytest.raises (state.StateError, match="Conflict markers remain"):
            conflicts.resolve (str (scratch), target, source, choice=conflicts.EDIT)
      finally:
         os.chdir (previous)

   def test_a_deletion_beats_a_stale_edit_by_default (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout")
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
      feature = _start (demo / "api", "checkout")
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


class TestHardening:

   def test_a_candidate_that_restores_a_deleted_path_is_blocked (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout")
      commit_file (Path (feature ["path"]), "file.txt", "still wanted\n", "feat: keep editing the file")
      git_run (demo / "api", "rm", "file.txt")
      git_run (demo / "api", "commit", "-m", "chore: drop the file")
      git_run (demo / "api", "push", "origin", "master")
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         from imp_git import integration
         plan = integration.plan_done (
            features.find (str (feature ["feature_id"])),
            actor_id="actor:human:anders",
            strategy="squash",
            resolve="theirs",
            persist=False,
         )

         assert plan ["payload"] ["resurrected"] == [ "file.txt" ]
         assert any ("restores" in value for value in plan ["blockers"])
      finally:
         os.chdir (previous)

   def test_honouring_a_deletion_leaves_nothing_to_block (self, demo, tmp_path):
      feature = _start (demo / "api", "checkout")
      commit_file (Path (feature ["path"]), "file.txt", "still wanted\n", "feat: keep editing the file")
      git_run (demo / "api", "rm", "file.txt")
      git_run (demo / "api", "commit", "-m", "chore: drop the file")
      git_run (demo / "api", "push", "origin", "master")
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         from imp_git import integration
         plan = integration.plan_done (
            features.find (str (feature ["feature_id"])),
            actor_id="actor:human:anders",
            strategy="squash",
            resolve="resolve",
            persist=False,
         )

         assert plan ["payload"] ["resurrected"] == []
         assert plan ["blockers"] == []
      finally:
         os.chdir (previous)

   def test_an_undeletable_worktree_leaves_the_integration_landed (self, demo, tmp_path, monkeypatch):
      feature = _start (demo / "api", "checkout")
      commit_file (Path (feature ["path"]), "new.txt", "work\n", "feat: work")
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         import subprocess as sp
         monkeypatch.setattr (
            features.git, "worktree_remove",
            lambda *a, **k: (_ for _ in ()).throw (sp.CalledProcessError (255, "git")),
         )

         record = features.complete (features.find (str (feature ["feature_id"])), "actor:human:anders")

         assert record ["state"] == "completed"
         assert Path (feature ["path"]).exists ()
      finally:
         os.chdir (previous)

   def test_stale_scratch_worktrees_are_swept (self, demo, tmp_path, monkeypatch):
      from imp_git import integration
      scratch = Path (tmp_path / "tmp")
      scratch.mkdir ()
      stale = scratch / "imp-resolve-old"
      stale.mkdir ()
      fresh = scratch / "imp-resolve-new"
      fresh.mkdir ()
      os.utime (stale, (0, 0))
      monkeypatch.setattr (integration.tempfile, "gettempdir", lambda: str (scratch))
      monkeypatch.setattr (integration.git, "prune_worktrees", lambda: None)

      integration._sweep_stale ()

      assert not stale.exists ()
      assert fresh.exists ()


class TestInterrupted:

   def _record (self, repository: Path, candidate: str = "0" * 40, target: str = "master"):
      previous = Path.cwd ()
      os.chdir (repository)
      try:
         from imp_git import state as state_mod
         state_mod.atomic_write (state_mod.root () / "recovery" / "recovery--done--checkout--1.json", {
            "schema": "imp.recovery.v1",
            "recovery_id": "recovery:done:checkout:1",
            "command": "imp done",
            "label": "checkout",
            "candidate_oid": candidate,
            "target_ref": target,
            "completed": [],
            "error": "Target worktree is dirty",
            "next": "imp done checkout",
            "created_at": "2026-08-17T00:00:00Z",
         })
      finally:
         os.chdir (previous)


   def test_a_resumable_operation_is_listed (self, demo):
      self._record (demo / "api")
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         from imp_git import state as state_mod

         assert [ record ["command"] for record in state_mod.recoveries () ] == [ "imp done" ]
      finally:
         os.chdir (previous)



   def test_a_landed_candidate_expires_its_record (self, demo):
      from imp_git import git
      from imp_git import state as state_mod

      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         landed = git.rev_parse ("master")
         self._record (demo / "api", candidate=landed, target="master")

         assert state_mod.recoveries () == []
      finally:
         os.chdir (previous)

   def test_an_unlanded_candidate_keeps_its_record (self, demo, tmp_path):
      from imp_git import state as state_mod

      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         self._record (demo / "api", candidate="0" * 40, target="master")

         assert [ r ["command"] for r in state_mod.recoveries () ] == [ "imp done" ]
      finally:
         os.chdir (previous)

   def test_the_roster_gathers_them_across_repositories (self, demo):
      self._record (demo / "api")
      self._record (demo / "web")

      values = roster.interrupted (workspace.here (str (demo)))

      assert sorted (record ["alias"] for record in values) == [ "api", "web" ]


class TestDiscovery:

   def _repo (self, path: Path):
      path.mkdir (parents=True, exist_ok=True)
      git_run (path, "init", "-q", "-b", "main", ".")
      git_run (path, "config", "user.email", "t@t.com")
      git_run (path, "config", "user.name", "T")
      commit_file (path, "file.txt", "x\n", "chore: init")

   def test_nested_repositories_are_found_without_any_declaration (self, tmp_path, monkeypatch):
      root = tmp_path / "projects"
      self._repo (root / "alpha")
      self._repo (root / "group" / "beta")
      monkeypatch.chdir (root)

      value = workspace.here ()

      assert sorted (value ["services"]) == [ "alpha", "group/beta" ]

   def test_a_member_resolves_by_its_final_path_segment (self, tmp_path, monkeypatch):
      root = tmp_path / "projects"
      self._repo (root / "group" / "api.example.com")
      monkeypatch.chdir (root)
      value = workspace.here ()

      expected = ( "group/api.example.com", str (root / "group" / "api.example.com") )

      assert workspace.match (value, "api") == expected
      assert workspace.match (value, "api.example.com") == expected
      assert workspace.match (value, "group/api.example.com") == expected

   def test_an_ambiguous_name_is_refused_rather_than_guessed (self, tmp_path, monkeypatch):
      root = tmp_path / "projects"
      self._repo (root / "one" / "api")
      self._repo (root / "two" / "api")
      monkeypatch.chdir (root)
      value = workspace.here ()

      with pytest.raises (state.StateError, match="Ambiguous repository"):
         workspace.match (value, "api")

   def test_noise_directories_are_not_searched (self, tmp_path, monkeypatch):
      root = tmp_path / "projects"
      self._repo (root / "alpha")
      self._repo (root / "node_modules" / "package")
      self._repo (root / ".hidden" / "thing")
      monkeypatch.chdir (root)

      assert sorted (workspace.here () ["services"]) == [ "alpha" ]

   def test_a_directory_without_repositories_is_not_a_workspace (self, tmp_path, monkeypatch):
      root = tmp_path / "empty"
      root.mkdir ()
      monkeypatch.chdir (root)

      assert workspace.here () is None

   def test_members_report_branch_and_dirty_state (self, tmp_path, monkeypatch):
      root = tmp_path / "projects"
      self._repo (root / "alpha")
      (root / "alpha" / "loose.txt").write_text ("unsaved\n")
      monkeypatch.chdir (root)

      members = roster.repositories (workspace.here ())

      assert [ member ["alias"] for member in members ] == [ "alpha" ]
      assert members [0] ["branch"] == "main"
      assert members [0] ["dirty"] == 1
      assert members [0] ["tracked"] is False


class TestSpentState:

   def _repo_state (self, repository: Path):
      from imp_git import state as state_mod
      previous = Path.cwd ()
      os.chdir (repository)
      try:
         return state_mod.root ()
      finally:
         os.chdir (previous)

   def test_orphaned_state_from_removed_features_is_dropped (self, demo):
      from imp_git import state as state_mod

      root = self._repo_state (demo / "api")
      root.mkdir (parents=True, exist_ok=True)
      (root / "active.json").write_text ("{}")
      (root / "contexts").mkdir (parents=True, exist_ok=True)
      (root / "contexts" / "feature--old.md").write_text ("stale\n")
      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         state_mod.tidy ()
      finally:
         os.chdir (previous)

      assert not (root / "active.json").exists ()
      assert not (root / "contexts").exists ()
      assert not (root / "plans").exists ()




class TestIntegrateEvery:

   def _feature (self, repository: Path, name: str, work: str = "work\n"):
      previous = Path.cwd ()
      os.chdir (repository)
      try:
         from imp_git import repo as repo_mod
         repo_mod.load.cache_clear ()
         plan = features.plan_start (name, actor_id="actor:human:anders")
         created = features.apply_start (plan)
         commit_file (Path (created ["path"]), f"{name}.txt", work, f"feat: add {name}")
         return created
      finally:
         os.chdir (previous)
         from imp_git import repo as repo_mod
         repo_mod.load.cache_clear ()

   def test_every_ready_feature_lands_and_blocked_ones_are_skipped (self, demo, tmp_path, monkeypatch):
      from imp_git.commands import done as done_cmd

      self._feature (demo / "api", "first")
      self._feature (demo / "api", "second")
      dirty = self._feature (demo / "api", "third")
      (Path (dirty ["path"]) / "loose.txt").write_text ("unsaved\n")
      monkeypatch.chdir (demo)

      data = done_cmd._promote_every (
         "actor:human:anders", yes=True, dry_run=False, approve=False,
         skip_checks=True, strategy="squash", resolve="", warnings=[],
      )

      assert sorted (data ["landed"]) == [ "first", "second" ]
      assert data ["skipped"] == [ "third" ]

   def test_a_dry_run_lands_nothing (self, demo, tmp_path, monkeypatch):
      from imp_git.commands import done as done_cmd

      self._feature (demo / "api", "first")
      monkeypatch.chdir (demo)

      data = done_cmd._promote_every (
         "actor:human:anders", yes=True, dry_run=True, approve=False,
         skip_checks=True, strategy="squash", resolve="", warnings=[],
      )

      assert data ["landed"] == []
      assert data ["ready"] == [ "first" ]

   def test_a_record_that_names_no_candidate_is_dropped (self, demo):
      from imp_git import state as state_mod

      previous = Path.cwd ()
      os.chdir (demo / "api")
      try:
         state_mod.atomic_write (state_mod.root () / "recovery" / "recovery--done--legacy--1.json", {
            "schema": "imp.recovery.v1",
            "recovery_id": "recovery:done:legacy:1",
            "command": "imp done",
            "completed": [],
            "error": "Target worktree is dirty",
            "next": "imp done --apply plan:done:legacy:4 --yes",
            "created_at": "2026-08-16T00:00:00Z",
         })

         assert state_mod.recoveries () == []
      finally:
         os.chdir (previous)


class TestSpan:
   """One feature across several checkouts, discovered rather than declared."""

   def _ready (self, demo: Path):
      from imp_git.commands import start as start_cmd

      start_cmd.start (name="checkout", repos=[ "web", "api" ])
      for entry in roster.collect (workspace.here (str (demo))) [0] ["members"]:
         commit_file (Path (entry ["path"]), "new.txt", "work\n", "feat: work")

   def test_a_span_records_workspace_aliases_not_shorthand (self, demo, tmp_path, monkeypatch):
      from imp_git.commands import start as start_cmd

      nested = demo / "group"
      nested.mkdir ()
      _repo (nested, "api.example.com")
      _repo (nested, "web.example.com")
      monkeypatch.chdir (demo)

      data = start_cmd.start (name="nested", repos=[ "web.example.com", "api.example.com" ])

      assert data ["span"] == [ "group/web.example.com", "group/api.example.com" ]
      entry = next (e for e in roster.collect (workspace.here (str (demo))) if e ["name"] == "nested")
      assert [ member ["alias"] for member in roster.ordered_members (entry) ] == data ["span"]

   def test_a_span_starts_from_a_directory_of_checkouts (self, demo, tmp_path):
      from imp_git.commands import start as start_cmd

      data = start_cmd.start (name="checkout", repos=[ "web", "api" ])

      assert [ member ["alias"] for member in data ["members"] ] == [ "web", "api" ]
      entry = roster.collect (workspace.here (str (demo))) [0]
      assert entry ["span"] == [ "web", "api" ]
      assert [ member ["alias"] for member in roster.ordered_members (entry) ] == [ "web", "api" ]

   def test_a_span_dry_run_creates_nothing (self, demo, tmp_path):
      from imp_git.commands import start as start_cmd

      runtime.configure (dry_run=True, yes=True)
      start_cmd.start (name="checkout", repos=[ "api", "web" ])

      assert roster.collect (workspace.here (str (demo))) == []
      assert not (tmp_path / "worktrees").exists ()
      assert "checkout" not in git_run (demo / "api", "branch", "--list").stdout

   def test_a_span_refuses_to_prompt_without_approval (self, demo):
      from imp_git.commands import start as start_cmd

      runtime.configure (no_input=True)
      with pytest.raises (typer.Exit):
         start_cmd.start (name="checkout", repos=[ "api", "web" ])

      assert roster.collect (workspace.here (str (demo))) == []

   def test_a_failed_member_unwinds_the_whole_span (self, demo, monkeypatch):
      from imp_git.commands import start as start_cmd

      applied = []
      real = features.apply_start

      def flaky (plan):
         applied.append (plan)
         if len (applied) == 2:
            raise state.StateError ("second repository failed")
         return real (plan)

      monkeypatch.setattr (start_cmd.features, "apply_start", flaky)
      with pytest.raises (typer.Exit):
         start_cmd.start (name="checkout", repos=[ "api", "web" ])

      assert roster.collect (workspace.here (str (demo))) == []
      assert "checkout" not in git_run (demo / "api", "branch", "--list").stdout

   def test_integrating_a_span_emits_one_json_document (self, demo, capsys):
      from imp_git.commands import done as done_cmd

      self._ready (demo)
      runtime.configure (json=True, yes=True)
      capsys.readouterr ()
      done_cmd.done ("checkout", skip_checks=True)

      value = json.loads (capsys.readouterr ().out)
      assert value ["schema"] == "imp.promote.v2"
      assert value ["data"] ["order"] == [ "web", "api" ]
      assert value ["data"] ["completed"] == [ "web", "api" ]

   def test_integrating_a_span_refuses_to_prompt_without_approval (self, demo, capsys):
      from imp_git.commands import done as done_cmd

      self._ready (demo)
      runtime.configure (json=True, no_input=True)
      capsys.readouterr ()
      with pytest.raises (typer.Exit):
         done_cmd.done ("checkout", skip_checks=True)

      value = json.loads (capsys.readouterr ().out)
      assert value ["schema"] == "imp.error.v1"
      assert value ["ok"] is False

   def test_integrating_every_feature_emits_one_json_document (self, demo, capsys):
      from imp_git.commands import done as done_cmd

      self._ready (demo)
      runtime.configure (json=True, yes=True)
      capsys.readouterr ()
      done_cmd.done (all_ready=True, skip_checks=True)

      value = json.loads (capsys.readouterr ().out)
      assert value ["schema"] == "imp.promote-all.v1"
      assert value ["data"] ["landed"] == [ "checkout" ]

   def _require_review (self, demo: Path):
      from imp_git import repo as repo_mod

      for alias in [ "api", "web" ]:
         commit_file (demo / alias, ".imp", '{ "review:required": true }\n', "chore: require review")
      repo_mod.load.cache_clear ()

   def test_an_unreviewed_span_is_blocked (self, demo, capsys):
      from imp_git.commands import done as done_cmd

      self._require_review (demo)
      self._ready (demo)
      runtime.configure (json=True, yes=True)
      capsys.readouterr ()

      with pytest.raises (typer.Exit):
         done_cmd.done ("checkout", skip_checks=True)

      assert json.loads (capsys.readouterr ().out) ["schema"] == "imp.error.v1"

   def test_approving_clears_the_review_blocker (self, demo, capsys):
      from imp_git.commands import done as done_cmd

      self._require_review (demo)
      self._ready (demo)
      runtime.configure (json=True, yes=True)
      capsys.readouterr ()

      done_cmd.done ("checkout", skip_checks=True, approve=True)

      value = json.loads (capsys.readouterr ().out)
      assert value ["schema"] == "imp.promote.v2"
      assert value ["data"] ["completed"] == [ "web", "api" ]

   def test_declining_records_no_approval (self, demo, monkeypatch):
      from imp_git import integration
      from imp_git.commands import done as done_cmd

      self._ready (demo)
      runtime.configure ()
      monkeypatch.setattr (done_cmd.console, "confirm", lambda message: False)

      with pytest.raises (typer.Exit):
         done_cmd.done ("checkout", skip_checks=True, approve=True)

      for alias in [ "api", "web" ]:
         with workspace.inside (str (demo / alias)):
            assert integration.approval_receipt ("feature:checkout") is None

   def test_a_lone_checkout_is_a_workspace_of_one (self, repo_with_origin):
      value = workspace.here ()

      assert value is not None
      assert list (value ["services"]) == [ Path (value ["root"]).name ]

   def test_a_workspace_of_one_follows_the_path_it_was_given (self, demo, monkeypatch):
      monkeypatch.chdir (demo / "web")

      value = workspace.here (str (demo / "api"))

      assert list (value ["services"]) == [ "api" ]
      assert value ["root"] == str (demo / "api")
