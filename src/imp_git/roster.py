from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from imp_git import features, git, repo, spans, state, workspace

READY = "ready"
CHECKS = "checks"
CONFLICT = "conflict"
DIRTY = "dirty"
EMPTY = "empty"
BROKEN = "broken"

_ORDER = { READY: 0, CONFLICT: 1, CHECKS: 2, DIRTY: 3, EMPTY: 4, BROKEN: 5 }


def _age (value: str) -> str:
   try:
      created = datetime.fromisoformat (str (value).replace ("Z", "+00:00"))
   except ValueError:
      return ""
   delta = datetime.now (timezone.utc) - created
   hours = int (delta.total_seconds () // 3600)
   if hours < 1:
      return f"{int (delta.total_seconds () // 60)}m"
   if hours < 48:
      return f"{hours}h"
   return f"{hours // 24}d"


def _ahead (path: str, branch: str, target: str) -> int:
   output = git.run_at (path, "rev-list", "--count", f"{target}..{branch}", check=False)
   value = output.stdout.strip ()

   return int (value) if value.isdigit () else 0


def _member (feature: dict [str, Any], alias: str, repository: str) -> dict [str, Any]:
   path = str (feature ["path"])
   branch = str (feature ["branch"])
   target = str (feature.get ("target") or repo.get ("done:target", "")) or git.base_branch ()
   live = feature.get ("worktree_state") == "live"
   dirty = 0 if not live else len (git.run_at (path, "status", "--porcelain", check=False).stdout.splitlines ())
   ahead = _ahead (path, branch, target) if live else 0
   claim = feature.get ("claim") or {}

   if not live:
      condition = BROKEN
   elif dirty:
      condition = DIRTY
   elif not ahead:
      condition = EMPTY
   else:
      condition = READY

   return {
      "ahead": ahead,
      "alias": alias,
      "branch": branch,
      "condition": condition,
      "dirty": dirty,
      "feature_id": feature ["feature_id"],
      "path": path,
      "repository": repository,
      "repository_name": git.repo_name (),
      "target": target,
      "worktree_state": feature.get ("worktree_state"),
      "writer": claim.get ("held_by", "") if claim else "",
   }


def collect (value: dict [str, Any]) -> list [dict [str, Any]]:
   """Every open managed feature across the workspace, grouped by name."""

   grouped: dict [str, dict [str, Any]] = {}
   recorded = { str (span ["name"]): span for span in spans.all (value) }

   for alias, repository in sorted (workspace.repositories (value).items ()):
      if not Path (repository, ".git").exists ():
         continue
      with spans.inside (repository):
         for feature in features.all ():
            if feature.get ("state") not in { "active", "awaiting-merge" }:
               continue
            name = str (feature ["name"])
            entry = grouped.setdefault (name, {
               "name": name,
               "created_at": feature.get ("created_at", ""),
               "members": [],
               "spanned": name in recorded,
            })
            entry ["members"].append (_member (feature, alias, repository))
            if str (feature.get ("created_at", "")) < str (entry ["created_at"]):
               entry ["created_at"] = feature.get ("created_at", "")

   values = []
   for entry in grouped.values ():
      conditions = { member ["condition"] for member in entry ["members"] }
      for condition in [ BROKEN, DIRTY, EMPTY, READY ]:
         if condition in conditions:
            entry ["condition"] = condition
            break
      entry ["age"] = _age (str (entry ["created_at"]))
      entry ["repositories"] = sorted (member ["alias"] for member in entry ["members"])
      entry ["writers"] = sorted ({ member ["writer"] for member in entry ["members"] if member ["writer"] })
      entry ["members"] = sorted (entry ["members"], key=lambda member: member ["alias"])
      values.append (entry)

   return sorted (values, key=lambda entry: (_ORDER.get (entry ["condition"], 9), str (entry ["created_at"])))


def interrupted (value: dict [str, Any]) -> list [dict [str, Any]]:
   """Every unfinished operation across the workspace, newest last."""

   values = []
   for alias, repository in sorted (workspace.repositories (value).items ()):
      if not Path (repository, ".git").exists ():
         continue
      with spans.inside (repository):
         values.extend ({ "alias": alias, **record } for record in state.recoveries ())

   return sorted (values, key=lambda record: str (record.get ("created_at", "")))


def promotable (values: list [dict [str, Any]]) -> list [dict [str, Any]]:
   return [ entry for entry in values if entry ["condition"] == READY ]


def ordered_members (value: dict [str, Any], entry: dict [str, Any]) -> list [dict [str, Any]]:
   """Return one feature's members in dependency-first order."""

   by_alias = { member ["alias"]: member for member in entry ["members"] }
   try:
      ordered = workspace.order (value, sorted (by_alias))
   except state.StateError:
      ordered = sorted (by_alias)

   return [ by_alias [alias] for alias in ordered ]
