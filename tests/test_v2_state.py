from pathlib import Path

import pytest

from imp_git import identity, state
from imp_git import repo as repo_mod
from imp_git.commands import config as config_cmd


def _upgrade (value):
   return { **value, "schema": "imp.fixture.v1", "value": value.get ("old_value") }


class TestStateMigration:

   def test_v0_migrates_atomically_and_keeps_one_backup (self, repo):
      path = state.root () / "fixtures" / "example.json"
      state.atomic_write (path, { "old_value": "kept", "unknown": True })

      value = state.read (path, "imp.fixture.v1", { "v0": _upgrade })

      assert value ["value"] == "kept"
      assert value ["unknown"] is True
      assert len (list ((state.root () / "backups").glob ("fixtures--example--*.json"))) == 1

      assert state.read (path, "imp.fixture.v1") == value
      assert list ((state.root () / "backups").glob ("fixtures--example--*.json")) == []

   def test_migration_is_idempotent (self, repo):
      path = state.root () / "fixtures" / "example.json"
      state.atomic_write (path, { "old_value": "kept" })

      first = state.read (path, "imp.fixture.v1", { "v0": _upgrade })
      second = state.read (path, "imp.fixture.v1", { "v0": _upgrade })

      assert first == second

   def test_failed_migration_preserves_source (self, repo):
      path = state.root () / "fixtures" / "example.json"
      original = { "old_value": "kept" }
      state.atomic_write (path, original)

      def fail (value):
         raise RuntimeError ("broken fixture")

      with pytest.raises (RuntimeError, match="broken fixture"):
         state.read (path, "imp.fixture.v1", { "v0": fail })

      assert state.read (path) == original

   def test_unknown_newer_schema_requests_update (self, repo):
      path = Path (state.root (), "fixtures", "example.json")
      state.atomic_write (path, { "schema": "imp.fixture.v2" })

      with pytest.raises (state.StateError, match="update Imp"):
         state.read (path, "imp.fixture.v1")


class TestRepositoryConfigMigration:

   def test_committed_policy_requires_an_explicit_plan (self, repo):
      path = repo / ".imp"
      path.write_text ('{"feature:required": false}\n')
      repo_mod.load.cache_clear ()
      actor_id = identity.resource ("actor", "human", "anders")

      plan = config_cmd._migration_plan (actor_id, persist=True)

      assert "schema" not in repo_mod.load ()
      assert plan ["payload"] ["policy"] ["schema"] == "imp.config.v1"

      result = config_cmd._apply_migration (plan, actor_id)

      assert result ["schema"] == "imp.config.v1"
      assert repo_mod.load () ["schema"] == "imp.config.v1"
