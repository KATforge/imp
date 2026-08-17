import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from imp_git import identity, repo, state, workspace


def _directory (value: dict [str, Any]) -> Path:
   return state.workspace_root (str (value ["name"])) / "spans"


def _path (value: dict [str, Any], feature_id: str) -> Path:
   return _directory (value) / f"{identity.key (feature_id)}.json"


def all (value: dict [str, Any]) -> list [dict [str, Any]]:
   """List every multi-repository feature recorded for one workspace."""

   directory = _directory (value)
   if not directory.is_dir ():
      return []

   spans = []
   for path in sorted (directory.glob ("feature--*.json")):
      try:
         spans.append (state.read (path, "imp.span.v1"))
      except state.StateError:
         continue

   return sorted (spans, key=lambda span: str (span.get ("created_at", "")))


def find (value: dict [str, Any], name: str) -> dict [str, Any] | None:
   feature_id = name if name.startswith ("feature:") else identity.resource ("feature", identity.slug (name))
   path = _path (value, feature_id)
   if not path.is_file ():
      return None

   return state.read (path, "imp.span.v1")


def record (
   value: dict [str, Any],
   name: str,
   members: dict [str, str],
   actor_id: str,
) -> dict [str, Any]:
   """Persist which repositories one feature spans."""

   feature_id = identity.resource ("feature", identity.slug (name))
   span = {
      "schema": "imp.span.v1",
      "feature_id": feature_id,
      "name": identity.slug (name),
      "workspace": value ["name"],
      "members": {
         alias: { "alias": alias, "repository": repository }
         for alias, repository in sorted (members.items ())
      },
      "created_by": actor_id,
      "created_at": state.now (),
   }
   with state.lock (f"span-{identity.key (feature_id)}", base=state.workspace_root (str (value ["name"]))):
      state.atomic_write (_path (value, feature_id), span)

   return span


def forget (value: dict [str, Any], span: dict [str, Any]):
   _path (value, str (span ["feature_id"])).unlink (missing_ok=True)


def members (value: dict [str, Any], span: dict [str, Any]) -> list [dict [str, str]]:
   """Return one span's members in dependency-first order."""

   ordered = workspace.order (value, sorted (span ["members"]))

   return [ span ["members"] [alias] for alias in ordered ]


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
