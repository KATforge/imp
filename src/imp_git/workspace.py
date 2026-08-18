import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from imp_git import git, repo, state

SKIP = {
   ".git", ".venv", "__pycache__", "build", "dist", "node_modules", "obsolete",
   "target", "vendor", "venv",
}
DEPTH = 3


def _repositories_below (root: Path, depth: int) -> dict [str, str]:
   found: dict [str, str] = {}

   def walk (directory: Path, level: int):
      if level > depth:
         return
      try:
         entries = sorted (directory.iterdir ())
      except OSError:
         return
      for entry in entries:
         if not entry.is_dir () or entry.is_symlink () or entry.name in SKIP or entry.name.startswith ("."):
            continue
         if (entry / ".git").exists ():
            found [str (entry.relative_to (root))] = str (entry)
            continue
         walk (entry, level + 1)

   walk (root, 1)

   return found


def _containing (root: Path) -> dict [str, Any] | None:
   """Return the repository holding one directory as a workspace of one."""

   if not root.is_dir ():
      return None
   value = git.run_at (str (root), "rev-parse", "--show-toplevel", check=False).stdout.strip ()
   if not value:
      return None
   path = Path (value).resolve ()

   return {
      "name": path.name,
      "root": str (path),
      "services": { path.name: { "path": str (path) } },
   }


def here (start: str = "", depth: int = DEPTH) -> dict [str, Any] | None:
   """Return the repositories in scope, or None where there are none.

   A directory holding several checkouts is a workspace in practice, and a single
   checkout is a workspace of one. Imp declares nothing and reads no manifest, so
   membership is what is on disk and order is whatever the caller named.
   """

   root = Path (start).resolve () if start else Path.cwd ().resolve ()
   found = _repositories_below (root, depth)
   if not found:
      return _containing (root)

   return {
      "name": root.name.lstrip (".") or root.name,
      "root": str (root),
      "services": { alias: { "path": path } for alias, path in found.items () },
   }


def repositories (value: dict [str, Any]) -> dict [str, str]:
   """Return every member alias that still has a checkout on disk."""

   return {
      name: spec ["path"]
      for name, spec in value ["services"].items ()
      if spec ["path"] and Path (spec ["path"]).is_dir ()
   }


def match (value: dict [str, Any], name: str) -> str:
   """Resolve one member by alias, by its final path segment, or by suffix."""

   available = repositories (value)
   if name in available:
      return available [name]

   candidates = sorted (
      alias for alias in available
      if Path (alias).name == name or alias.endswith (f"/{name}") or Path (alias).name.startswith (f"{name}.")
   )
   if len (candidates) == 1:
      return available [candidates [0]]
   if candidates:
      raise state.StateError (f"Ambiguous repository {name}: {', '.join (candidates)}")

   raise state.StateError (f"Unknown repository: {name} (known: {', '.join (sorted (available))})")


@contextmanager
def inside (repository: str) -> Iterator [None]:
   """Run a block with one member repository as the working repository."""

   previous = Path.cwd ()
   os.chdir (repository)
   repo.load.cache_clear ()
   try:
      yield
   finally:
      os.chdir (previous)
      repo.load.cache_clear ()
