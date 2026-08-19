import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class StateError (RuntimeError):
   pass


def now () -> str:
   return datetime.now (timezone.utc).isoformat ().replace ("+00:00", "Z")


def stamp () -> str:
   """Return a refname-safe UTC timestamp."""

   return datetime.now (timezone.utc).strftime ("%Y%m%dT%H%M%SZ")


def temporary (prefix: str) -> Path:
   descriptor, value = tempfile.mkstemp (prefix=f"imp-{prefix}")
   os.close (descriptor)
   path = Path (value)
   path.unlink ()
   return path
