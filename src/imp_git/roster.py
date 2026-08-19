from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from imp_git import features, git, workspace

_ORDER = { "open": 0, "dirty": 1, "missing": 2 }


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


def _member (feature: dict [str, Any], alias: str, repository: str) -> dict [str, Any]:
   path = str (feature ["path"])
   branch = str (feature ["branch"])
   target = str (feature.get ("target") or git.base_branch ())
   live = feature.get ("worktree_state") == "live"
   dirty = 0 if not live else len (git.run_at (path, "status", "--porcelain", check=False).stdout.splitlines ())
   claim = feature.get ("claim") or {}

   return {
      "alias": alias,
      "branch": branch,
      "condition": "missing" if not live else "dirty" if dirty else "open",
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

   for alias, repository in sorted (workspace.repositories (value).items ()):
      if not Path (repository, ".git").exists ():
         continue
      with workspace.inside (repository):
         for feature in features.all ():
            if feature.get ("state") not in { "active", "awaiting-merge" }:
               continue
            name = str (feature ["name"])
            entry = grouped.setdefault (name, {
               "name": name,
               "created_at": feature.get ("created_at", ""),
               "members": [],
               "span": [],
            })
            entry ["span"] = entry ["span"] or list (feature.get ("span") or [])
            entry ["members"].append (_member (feature, alias, repository))
            if str (feature.get ("created_at", "")) < str (entry ["created_at"]):
               entry ["created_at"] = feature.get ("created_at", "")

   values = []
   for entry in grouped.values ():
      entry ["condition"] = max (
         (member ["condition"] for member in entry ["members"]),
         key=lambda condition: _ORDER [condition],
      )
      entry ["age"] = _age (str (entry ["created_at"]))
      entry ["repositories"] = sorted (member ["alias"] for member in entry ["members"])
      entry ["writers"] = sorted ({ member ["writer"] for member in entry ["members"] if member ["writer"] })
      entry ["members"] = ordered_members (entry)
      values.append (entry)

   return sorted (values, key=lambda entry: (_ORDER.get (entry ["condition"], 9), str (entry ["created_at"])))


def repositories (value: dict [str, Any]) -> list [dict [str, Any]]:
   """Summarise every member repository: its branch, drift, and uncommitted work."""

   values = []
   for alias, repository in sorted (workspace.repositories (value).items ()):
      if not Path (repository, ".git").exists ():
         continue
      with workspace.inside (repository):
         branch = git.branch ()
         upstream = f"origin/{branch}"
         tracked = bool (git.rev_parse (upstream))
         values.append ({
            "ahead": git.count_ahead () if tracked else 0,
            "alias": alias,
            "behind": git.count_behind () if tracked else 0,
            "branch": branch,
            "dirty": len (git.status_short ().splitlines ()),
            "path": repository,
            "tracked": tracked,
            "worktrees": max (0, len (git.worktrees ()) - 1),
         })

   return values


def ordered_members (entry: dict [str, Any]) -> list [dict [str, Any]]:
   """Return one feature's members in the order its span named, then by alias.

   A spanning feature records that order in every member, so integration follows the
   dependency the caller declared. Anything unnamed sorts after it.
   """

   rank = { alias: index for index, alias in enumerate (entry.get ("span") or []) }

   return sorted (entry ["members"], key=lambda member: (
      rank.get (str (member ["alias"]), len (rank)), str (member ["alias"]),
   ))
