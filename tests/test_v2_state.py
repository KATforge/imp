import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from imp_git import repo as repo_mod
from imp_git import state


def _upgrade (value):
   return { **value, "schema": "imp.fixture.v1", "value": value.get ("old_value") }


def _hold_lock (name, pid):
   path = state.root () / "locks" / f"{name}.json"
   path.parent.mkdir (parents=True, exist_ok=True)
   path.write_text (json.dumps ({
      "schema": "imp.lock.v1",
      "name": name,
      "pid": pid,
      "host": socket.gethostname (),
      "started_at": state.now (),
   }, indent=3, sort_keys=True) + "\n")
   return path


class TestLockContention:

   def test_live_second_process_contention_raises_after_bounded_retries (self, repo, monkeypatch):
      child = subprocess.Popen ([ sys.executable, "-c", "import time; time.sleep(60)" ])
      sleeps = []
      monkeypatch.setattr (state.time, "sleep", lambda value: sleeps.append (value))
      try:
         _hold_lock ("features", child.pid)
         with pytest.raises (state.StateError, match="locked by pid"), state.lock ("features", attempts=3, delay=0.01):
            pass
      finally:
         child.kill ()
         child.wait ()
      assert sleeps == [ 0.01, 0.02 ]

   def test_dead_second_process_lock_is_broken (self, repo):
      child = subprocess.Popen ([ sys.executable, "-c", "pass" ])
      child.wait ()
      _hold_lock ("features", child.pid)

      with state.lock ("features") as record:
         assert record ["pid"] == os.getpid ()

   def test_retry_acquires_after_the_holder_releases (self, repo, monkeypatch):
      child = subprocess.Popen ([ sys.executable, "-c", "import time; time.sleep(60)" ])
      try:
         path = _hold_lock ("features", child.pid)
         monkeypatch.setattr (state.time, "sleep", lambda value: path.unlink (missing_ok=True))

         with state.lock ("features", attempts=3, delay=0.01) as record:
            assert record ["name"] == "features"
      finally:
         child.kill ()
         child.wait ()


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


class TestRepositoryConfig:

   def test_committed_policy_needs_no_schema (self, repo):
      path = repo / ".imp"
      path.write_text ('{"feature:required": false}\n')
      repo_mod.load.cache_clear ()

      assert repo_mod.load () == { "feature:required": False }
