import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from imp_git import repo as repo_mod
from imp_git import state


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


class TestState:

   def test_unknown_newer_schema_requests_update (self, repo):
      path = Path (state.root (), "fixtures", "example.json")
      state.atomic_write (path, { "schema": "imp.fixture.v2" })

      with pytest.raises (state.StateError, match="update Imp"):
         state.read (path, "imp.fixture.v1")

   def test_obsolete_state_is_removed (self, repo):
      for name in ("backups", "claims", "recovery", "releases", "reviews", "temporary"):
         state.atomic_write (state.root () / name / "old.json", {})

      state.prune ()

      assert not any ((state.root () / name).exists () for name in (
         "backups", "claims", "recovery", "releases", "reviews", "temporary",
      ))

   def test_temporary_paths_are_outside_repository_state (self, repo):
      assert state.root () not in state.temporary ("test-").parents


class TestRepositoryConfig:

   def test_committed_policy_needs_no_schema (self, repo):
      path = repo / ".imp"
      path.write_text ('{"feature:required": false}\n')
      repo_mod.load.cache_clear ()

      assert repo_mod.load () == { "feature:required": False }
