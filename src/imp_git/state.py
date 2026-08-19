import json
import os
import socket
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from imp_git import git


class StateError (RuntimeError):
   pass


def now () -> str:
   return datetime.now (timezone.utc).isoformat ().replace ("+00:00", "Z")


def root () -> Path:
   common = Path (git.common_dir ())
   if not common.is_absolute ():
      common = Path (git.repo_root ()) / common
   return common.resolve () / "imp"


def temporary (prefix: str) -> Path:
   descriptor, value = tempfile.mkstemp (prefix=f"imp-{prefix}")
   os.close (descriptor)
   path = Path (value)
   path.unlink ()
   return path


def atomic_write (path: Path, value: dict [str, Any]):
   path.parent.mkdir (parents=True, exist_ok=True)
   temporary = path.with_name (f".{path.name}.{os.getpid ()}.tmp")
   try:
      with temporary.open ("w") as stream:
         stream.write (json.dumps (value, indent=3, sort_keys=True) + "\n")
         stream.flush ()
         os.fsync (stream.fileno ())
      temporary.chmod (0o600)
      temporary.replace (path)
   finally:
      temporary.unlink (missing_ok=True)


def read (path: Path, schema: str | None = None) -> dict [str, Any]:
   try:
      value = json.loads (path.read_text ())
   except FileNotFoundError as error:
      raise StateError (f"Missing Imp state: {path}") from error
   except (json.JSONDecodeError, OSError) as error:
      raise StateError (f"Invalid Imp state: {path}") from error
   if not isinstance (value, dict):
      raise StateError (f"Imp state must be an object: {path}")
   if schema and value.get ("schema") != schema:
      actual = str (value.get ("schema") or "unknown")
      if actual.startswith (schema.rsplit (".v", 1) [0] + ".v"):
         raise StateError (f"Unsupported newer schema {actual}; update Imp")
      raise StateError (f"Unsupported schema in {path}: {actual}")
   return value


def prune ():
   for name in ("backups", "claims", "recovery", "releases", "reviews", "temporary"):
      directory = root () / name
      if not directory.is_dir ():
         continue
      for path in directory.iterdir ():
         if path.is_file ():
            path.unlink ()
      with suppress (OSError):
         directory.rmdir ()


def _alive (pid: int) -> bool:
   try:
      os.kill (pid, 0)
   except ProcessLookupError:
      return False
   except PermissionError:
      return True
   return True


@contextmanager
def lock (name: str, *, attempts: int = 5, delay: float = 0.05) -> Iterator [dict [str, Any]]:
   path = root () / "locks" / f"{name}.json"
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
         stale = existing.get ("host") == socket.gethostname () and not _alive (int (existing.get ("pid", 0)))
         if stale:
            path.unlink (missing_ok=True)
            continue
         if attempt + 1 == attempts:
            raise StateError (
               f"Imp operation is locked by pid {existing.get ('pid')} on {existing.get ('host')}"
            ) from error
         time.sleep (delay * 2 ** attempt)
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
