from datetime import datetime, timedelta, timezone
from typing import Any

from imp_git import git, state

PREFIX = "refs/imp/layer"
DAYS = 30


def stage (bare: str, head: str, base: str) -> tuple [str, list [str]]:
   """Build the ref instructions recording one layer, for one atomic transaction.

   Callers splice these into the same `git.update_refs` call that moves trunk, so
   a landed layer and its undo record appear together or not at all. A layer that
   moved nothing stages nothing.
   """

   if not head or not base or head == base:
      return "", []
   root = f"{PREFIX}/{state.stamp ()}-{bare}"
   return root, [ f"create {root}/base {base}", f"create {root}/head {head}" ]


def record (bare: str, head: str, base: str) -> str:
   """Write one layer artifact: head and base refs naming exactly what landed.

   Both integration and trunk-session release write the same artifact, so
   `imp undo` has one format to consume regardless of how work reached trunk.
   """

   root, instructions = stage (bare, head, base)
   git.update_refs (instructions)
   return root


def _grouped () -> list [dict [str, Any]]:
   grouped: dict [str, dict [str, str]] = {}
   for ref, oid in git.refs (PREFIX).items ():
      root, _, kind = ref.rpartition ("/")
      if kind in ("head", "base"):
         grouped.setdefault (root, {}) [kind] = oid
   values = []
   for root in sorted (grouped, reverse=True):
      value = grouped [root]
      if "head" not in value or "base" not in value:
         continue
      stamped = root.rsplit ("/", 1) [-1]
      stamp, _, bare = stamped.partition ("-")
      values.append ({
         "bare": bare or stamped,
         "base": value ["base"],
         "head": value ["head"],
         "root": root,
         "stamp": stamp,
      })
   return values


def all () -> list [dict [str, Any]]:
   """Every complete layer, newest first."""

   return _grouped ()


def at_head (head: str) -> dict [str, Any] | None:
   """The layer whose head is exactly the given commit: the undoable top."""

   return next ((value for value in _grouped () if value ["head"] == head), None)


def consume (layer: dict [str, Any]):
   """Delete one undone layer's refs."""

   git.delete_ref_checked (f"{layer ['root']}/head", layer ["head"])
   git.delete_ref_checked (f"{layer ['root']}/base", layer ["base"])


def expire (days: int = DAYS) -> list [str]:
   """Drop layer refs older than the retention window and return what was removed."""

   cutoff = (datetime.now (timezone.utc) - timedelta (days=days)).strftime ("%Y%m%dT%H%M%SZ")
   removed = []
   for value in _grouped ():
      if value ["stamp"] < cutoff:
         consume (value)
         removed.append (value ["root"])
   return removed
