import json
import os
import shutil
import socket
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from imp_git import git


class StateError (RuntimeError):
   """Raised when persisted Imp state is missing, invalid, or locked."""


Migration = Callable [[dict [str, Any]], dict [str, Any]]


def now () -> str:
   """Return the current UTC time in the persisted timestamp format."""

   return datetime.now (timezone.utc).isoformat ().replace ("+00:00", "Z")


def root () -> Path:
   """Return the repository-local Imp state directory."""

   common = Path (git.common_dir ())
   if not common.is_absolute ():
      common = Path (git.repo_root ()) / common

   return common.resolve () / "imp"


def workspace_root (name: str) -> Path:
   """Return the user-level Imp state directory for one workspace."""

   base = os.environ.get ("XDG_STATE_HOME", "") or str (Path.home () / ".local" / "state")

   return Path (base) / "imp" / "workspaces" / name


def temporary (prefix: str) -> Path:
   """Reserve a unique path beneath tool-owned repository state."""

   directory = root () / "temporary"
   directory.mkdir (parents=True, exist_ok=True)
   descriptor, value = tempfile.mkstemp (prefix=prefix, dir=directory)
   os.close (descriptor)
   path = Path (value)
   path.unlink ()
   return path


def atomic_write (path: Path, value: dict [str, Any]):
   """Atomically replace one JSON document in its owning directory."""

   path.parent.mkdir (parents=True, exist_ok=True)
   temporary = path.with_name (f".{path.name}.{os.getpid ()}.tmp")
   payload = json.dumps (value, indent=3, sort_keys=True) + "\n"

   try:
      with temporary.open ("w") as stream:
         stream.write (payload)
         stream.flush ()
         os.fsync (stream.fileno ())
      temporary.chmod (0o600)
      temporary.replace (path)
   finally:
      temporary.unlink (missing_ok=True)


def _load (path: Path) -> dict [str, Any]:
   try:
      value = json.loads (path.read_text ())
   except FileNotFoundError as error:
      raise StateError (f"Missing Imp state: {path}") from error
   except (json.JSONDecodeError, OSError) as error:
      raise StateError (f"Invalid Imp state: {path}") from error

   if not isinstance (value, dict):
      raise StateError (f"Imp state must be an object: {path}")
   return value


def _backup_prefix (path: Path) -> str:
   return f"{path.parent.name}--{path.stem}--"


def _backup (path: Path, value: dict [str, Any]):
   stamp = datetime.now (timezone.utc).strftime ("%Y%m%dT%H%M%S%fZ")
   atomic_write (root () / "backups" / f"{_backup_prefix (path)}{stamp}.json", value)


def _clear_backups (path: Path):
   directory = root () / "backups"
   if not directory.exists ():
      return
   for backup in directory.glob (f"{_backup_prefix (path)}*.json"):
      backup.unlink ()


def _migrate (
   path: Path,
   value: dict [str, Any],
   schema: str,
   migrations: dict [str, Migration],
) -> dict [str, Any]:
   with lock (f"migration-{path.parent.name}-{path.stem}"):
      current = _load (path)
      source = str (current.get ("schema") or "v0")
      if current != value:
         raise StateError (f"Imp state changed before migration: {path}")
      original = dict (current)
      seen = set ()
      while source != schema:
         if source in seen or source not in migrations:
            raise StateError (f"No migration from {source} to {schema} for {path}")
         seen.add (source)
         current = migrations [source] (dict (current))
         if not isinstance (current, dict):
            raise StateError (f"Migration did not return an object: {path}")
         next_schema = str (current.get ("schema") or "v0")
         if next_schema == source:
            raise StateError (f"Migration did not advance schema {source}: {path}")
         source = next_schema
      candidate = path.with_name (f".{path.name}.{os.getpid ()}.migration")
      try:
         atomic_write (candidate, current)
         validated = _load (candidate)
         if validated.get ("schema") != schema:
            raise StateError (f"Migration validation failed for {path}")
         _backup (path, original)
         candidate.replace (path)
         return validated
      finally:
         candidate.unlink (missing_ok=True)


def read (
   path: Path,
   schema: str | None = None,
   migrations: dict [str, Migration] | None = None,
) -> dict [str, Any]:
   """Read, validate, and optionally migrate one Imp JSON document."""

   value = _load (path)
   if not schema:
      return value
   actual = str (value.get ("schema") or "v0")
   if actual == schema:
      _clear_backups (path)
      return value
   if migrations and actual in migrations:
      return _migrate (path, value, schema, migrations)
   if actual.startswith (schema.rsplit (".v", 1) [0] + ".v"):
      raise StateError (f"Unsupported newer schema {actual}; update Imp")
   raise StateError (f"Unsupported schema in {path}: {actual}")


def _landed (candidate: str, target: str) -> bool:
   """Return whether one candidate commit is already part of its target branch."""

   from imp_git import git

   if not candidate or not target:
      return False

   return git.succeeds ("merge-base", "--is-ancestor", candidate, target)




def tidy ():
   """Drop state that is spent or orphaned by a removed feature."""

   directory = root ()
   (directory / "active.json").unlink (missing_ok=True)
   shutil.rmtree (directory / "contexts", ignore_errors=True)

   shutil.rmtree (directory / "plans", ignore_errors=True)


def recoveries () -> list [dict [str, Any]]:
   """List interrupted operations, dropping any whose work has since landed.

   A record carries the candidate it was building and the target it was building
   onto. When the target already contains that candidate the operation finished,
   however the run ended, so the record is noise.

   Records written before that became true describe nothing actionable: they name no
   candidate, and their resume hint points at a saved plan that no longer exists. They
   are dropped rather than reported forever.
   """

   directory = root () / "recovery"
   if not directory.is_dir ():
      return []

   values = []
   for path in sorted (directory.glob ("*.json")):
      try:
         record = read (path, "imp.recovery.v1")
      except StateError:
         path.unlink (missing_ok=True)
         continue
      if not record.get ("candidate_oid") or "--apply" in str (record.get ("next", "")):
         path.unlink (missing_ok=True)
         continue
      if _landed (record.get ("candidate_oid", ""), record.get ("target_ref", "")):
         path.unlink (missing_ok=True)
         continue
      values.append (record)

   return sorted (values, key=lambda value: str (value.get ("created_at", "")))


def clear_recovery (label: str):
   """Remove recovery records for one operation that has since succeeded."""

   directory = root () / "recovery"
   if not directory.is_dir ():
      return
   for path in directory.glob ("*.json"):
      try:
         value = read (path)
      except StateError:
         continue
      if value.get ("label") == label:
         path.unlink ()


def _process_exists (pid: int) -> bool:
   try:
      os.kill (pid, 0)
   except ProcessLookupError:
      return False
   except PermissionError:
      return True

   return True


def _stale (record: dict [str, Any]) -> bool:
   return record.get ("host") == socket.gethostname () and not _process_exists (int (record.get ("pid", 0)))


@contextmanager
def lock (name: str, *, base: Path | None = None, attempts: int = 5, delay: float = 0.05) -> Iterator [dict [str, Any]]:
   """Acquire one advisory lock for a bounded mutation."""

   path = (base or root ()) / "locks" / f"{name}.json"
   path.parent.mkdir (parents=True, exist_ok=True)
   record = {
      "schema": "imp.lock.v1",
      "name": name,
      "pid": os.getpid (),
      "host": socket.gethostname (),
      "started_at": now (),
   }

   for attempt in range (attempts):
      try:
         descriptor = os.open (path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
      except FileExistsError as error:
         try:
            existing = read (path, "imp.lock.v1")
         except StateError:
            time.sleep (delay)
            continue
         if _stale (existing):
            path.unlink (missing_ok=True)
            continue
         if attempt + 1 == attempts:
            raise StateError (
               f"Imp operation is locked by pid {existing.get ('pid')} on {existing.get ('host')}"
            ) from error
         time.sleep (delay * (2 ** attempt))
         continue

      with os.fdopen (descriptor, "w") as stream:
         stream.write (json.dumps (record, indent=3, sort_keys=True) + "\n")
      break
   else:
      raise StateError (f"Unable to acquire Imp lock: {name}")

   try:
      yield record
   finally:
      try:
         current = read (path, "imp.lock.v1")
      except StateError:
         current = {}
      if current.get ("pid") == os.getpid () and current.get ("host") == socket.gethostname ():
         path.unlink (missing_ok=True)
