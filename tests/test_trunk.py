from pathlib import Path

import pytest

from imp_git import ai, commit_plan, features, git, integration, locks, state
from imp_git.commands import cleanup as cleanup_cmd
from imp_git.commands import done as done_cmd
from imp_git.commands import start as start_cmd
from tests.conftest import commit_file, git_run

FOREIGN = "task actor:claude:other 2099-01-01T00:00:00Z"
EXPIRED = "task actor:claude:other 2000-01-01T00:00:00Z"


class TestTrunkFirst:

   def test_start_claims_free_trunk (self, repo):
      data = start_cmd.start (name="quick fix")

      assert data ["mode"] == "trunk"
      assert data ["trunk"] == "main"
      lock = locks.holder ("main")
      assert lock ["name"] == "quick-fix"
      assert git.branch_names ("feature/*") == []

   def test_start_falls_back_when_trunk_is_locked (self, repo):
      git_run (repo, "config", "imp.lock.main.holder", FOREIGN)

      data = start_cmd.start (name="quick")

      assert data ["mode"] == "worktree"
      assert git.ref_exists ("feature/quick")

   def test_start_falls_back_when_trunk_is_dirty (self, repo):
      (repo / "loose.txt").write_text ("loose\n")

      data = start_cmd.start (name="quick")

      assert data ["mode"] == "worktree"
      assert locks.holder ("main") is None

   def test_worktree_flag_forces_isolation (self, repo):
      data = start_cmd.start (name="quick", worktree=True)

      assert data ["mode"] == "worktree"

   def test_ticket_rides_the_trunk_lock (self, repo):
      data = start_cmd.start (name="quick", ticket="SPK-9")

      assert data ["mode"] == "trunk"
      lock = locks.holder ("main")
      assert lock ["ticket"] == "SPK-9"
      assert lock ["base"] == git.rev_parse ("main")

   def test_expired_foreign_lock_is_free (self, repo):
      git_run (repo, "config", "imp.lock.main.holder", EXPIRED)

      data = start_cmd.start (name="quick")

      assert data ["mode"] == "trunk"
      assert locks.holder ("main") ["actor"].startswith ("actor:human:")


class TestTrunkCommits:

   def test_commit_on_trunk_renews_my_lock (self, repo, monkeypatch):
      start_cmd.start (name="quick")
      (repo / "file.txt").write_text ("changed\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      commit_plan.apply (commit_plan.create ())

      lock = locks.holder ("main")
      assert lock ["name"] == "quick"
      assert git.log_oneline (count=1).endswith ("fix: update value")

   def test_commit_on_trunk_claims_without_start (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      commit_plan.apply (commit_plan.create ())

      assert locks.holder ("main") ["name"] == "main"

   def test_commit_on_trunk_is_blocked_by_a_foreign_lock (self, repo):
      git_run (repo, "config", "imp.lock.main.holder", FOREIGN)
      (repo / "file.txt").write_text ("changed\n")

      with pytest.raises (state.StateError, match="locked by"):
         commit_plan.create (message="fix: update value")

   def test_commit_in_a_worktree_ignores_the_trunk_lock (self, repo, monkeypatch):
      git_run (repo, "config", "imp.lock.main.holder", FOREIGN)
      feature = features.apply_start (features.plan_start ("isolated"))
      monkeypatch.chdir (feature ["path"])
      Path ("new.txt").write_text ("new\n")

      result = commit_plan.apply (commit_plan.create (message="feat: add new file"))

      assert result ["branch"] == "feature/isolated"
      assert git.capture ("show", "feature/isolated:new.txt").strip () == "new"


class TestTrunkRelease:

   def test_done_releases_my_lock (self, repo):
      start_cmd.start (name="quick")

      receipt = done_cmd.done ()

      assert receipt ["released"] == [ "main" ]
      assert locks.holder ("main") is None

   def test_done_releases_by_name (self, repo):
      start_cmd.start (name="quick")

      receipt = done_cmd.done ("quick")

      assert receipt ["released"] == [ "main" ]

   def test_bare_done_finishes_my_trunk_session_first (self, repo):
      start_cmd.start (name="quick")
      feature = features.apply_start (features.plan_start ("real"))
      commit_file (Path (feature ["path"]), "real.txt", "real\n", "feat: add real work")

      receipt = done_cmd.done ()

      assert receipt ["released"] == [ "main" ]
      assert locks.holder ("main") is None

      receipt = done_cmd.done ()

      assert receipt ["completed"] == [ "real" ]

   def test_integration_is_blocked_by_a_foreign_lock (self, repo):
      feature = features.apply_start (features.plan_start ("blocked"))
      commit_file (Path (feature ["path"]), "b.txt", "b\n", "feat: add blocked work")
      git_run (repo, "config", "imp.lock.main.holder", FOREIGN)

      plan = integration.plan_done (features.find ("blocked"))

      assert any ("locked by" in blocker for blocker in plan ["blockers"])

   def test_cleanup_sweeps_expired_locks (self, repo):
      git_run (repo, "config", "imp.lock.main.holder", EXPIRED)

      cleanup_cmd.cleanup ()

      assert git.config_get ("imp.lock.main.holder") == ""


class TestTrunkSessions:

   def test_a_released_session_is_one_undoable_layer (self, repo):
      from imp_git import layers
      from imp_git.commands import undo as undo_cmd

      before = git.rev_parse ("main")
      start_cmd.start (name="quick")
      commit_file (repo, "quick.txt", "quick\n", "feat: add quick change")
      landed = git.rev_parse ("main")

      done_cmd.done ()

      layer = layers.at_head (landed)
      assert layer ["bare"] == "quick"
      assert layer ["base"] == before

      receipt = undo_cmd.undo ()

      assert git.rev_parse ("main") == before
      assert git.rev_parse ("feature/quick") == landed
      assert receipt ["path"]
      assert layers.all () == []

   def test_a_live_session_can_be_undone_midway (self, repo):
      from imp_git.commands import undo as undo_cmd

      before = git.rev_parse ("main")
      start_cmd.start (name="risky", ticket="SPK-7")
      commit_file (repo, "risky.txt", "risky\n", "feat: add risky change")

      undo_cmd.undo ()

      assert git.rev_parse ("main") == before
      assert git.ref_exists ("feature/SPK-7-risky")
      assert locks.holder ("main") is None

   def test_a_dirty_session_refuses_to_release (self, repo):
      import typer

      start_cmd.start (name="quick")
      (repo / "loose.txt").write_text ("loose\n")

      with pytest.raises (typer.Exit):
         done_cmd.done ()

      assert locks.holder ("main") is not None

   def test_an_empty_session_records_no_layer (self, repo):
      from imp_git import layers

      start_cmd.start (name="idle")

      done_cmd.done ()

      assert layers.all () == []

   def test_trunk_commits_carry_the_lock_ticket (self, repo, monkeypatch):
      seen = {}

      def spy (prompt):
         seen ["prompt"] = prompt
         return "fix: SPK-9 update value"

      start_cmd.start (name="quick", ticket="SPK-9")
      (repo / "file.txt").write_text ("changed\n")
      monkeypatch.setattr (ai, "fast", spy)

      commit_plan.apply (commit_plan.create ())

      assert "SPK-9" in seen ["prompt"]


class TestRegressions:

   def test_diffs_with_markup_render_verbatim (self):
      from imp_git import console

      console.raw ("+ out.print (f\"[/{'style'}]\") [bold [/nope]")

   def test_worktree_path_is_never_wrapped (self, repo, capsys):
      from imp_git.commands import worktree as worktree_cmd

      name = "a-very-long-feature-name-that-would-certainly-exceed-an-eighty-column-terminal-width-limit"
      features.apply_start (features.plan_start (name))
      capsys.readouterr ()

      path = worktree_cmd.path (name)

      assert capsys.readouterr ().out == path + "\n"
