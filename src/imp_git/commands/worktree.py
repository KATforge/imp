from pathlib import Path
from typing import Annotated

import typer

from imp_git import console, features, git, identity, result, runtime, state, workspace
from imp_git.cli import SortedCommand

worktree = typer.Typer (
   name="worktree",
   help="Inspect and manage linked worktrees",
   no_args_is_help=True,
)


def _collect (alias: str = "") -> list [dict]:
   managed = { str (Path (feature ["path"]).resolve ()): feature for feature in features.all () }
   values = []
   for entry in git.worktrees ():
      path = str (Path (entry.get ("worktree", "")).resolve ())
      feature = managed.get (path)
      values.append ({
         "alias": alias,
         "branch": entry.get ("branch", "").removeprefix ("refs/heads/"),
         "feature_id": feature.get ("feature_id") if feature else None,
         "name": feature.get ("name") if feature else ("trunk" if not values else "unmanaged"),
         "path": path,
         "state": feature.get ("worktree_state", "live") if feature else "unmanaged",
         "target": feature.get ("target") if feature else None,
      })

   return values


def _across_workspace (json_output: bool):
   """List every worktree in every repository below a multi-project root."""

   value = workspace.here ()
   if not value:
      console.fatal ("Not a git repository, and no repositories below this directory")

   values = []
   for alias, repository in sorted (workspace.repositories (value).items ()):
      if not Path (repository, ".git").exists ():
         continue
      with workspace.inside (repository):
         values.extend (entry for entry in _collect (alias) if entry ["name"] != "trunk")

   if json_output:
      return result.emit ("imp.worktrees.v2", "imp worktree list", { "worktrees": values }, json_output=True)
   if not values:
      console.muted (f"No feature worktrees below {value ['root']}")
      return { "worktrees": values }
   console.table (
      [ "Repository", "Feature", "Branch", "Path", "State" ],
      [
         [ str (v ["alias"]), str (v ["name"]), v ["branch"], v ["path"], v ["state"] ]
         for v in values
      ],
   )

   return { "worktrees": values }


@worktree.command ("list", cls=SortedCommand)
def list_ (

):
   """List repository worktrees and their managed feature state."""

   json_output = runtime.options.json

   if not git.succeeds ("rev-parse", "--git-dir"):
      return _across_workspace (json_output)

   git.require ()
   here = str (Path.cwd ().resolve ())
   managed = { str (Path (feature ["path"]).resolve ()): feature for feature in features.all () }
   rows = []
   values = []
   for entry in git.worktrees ():
      path = str (Path (entry.get ("worktree", "")).resolve ())
      feature = managed.get (path)
      value = {
         "here": here == path or here.startswith (path + "/"),
         "branch": entry.get ("branch", "").removeprefix ("refs/heads/"),
         "feature_id": feature.get ("feature_id") if feature else None,
         "name": feature.get ("name") if feature else ("trunk" if not values else "unmanaged"),
         "path": path,
         "state": feature.get ("worktree_state", "live") if feature else "unmanaged",
         "target": feature.get ("target") if feature else None,
      }
      values.append (value)
      rows.append ([ "*" if value ["here"] else "", str (value ["name"]), value ["branch"], path, value ["state"] ])
   if json_output:
      return result.emit ("imp.worktrees.v2", "imp worktree list", { "worktrees": values }, json_output=True)
   console.table ([ "Here", "Feature", "Branch", "Path", "State" ], rows)
   return { "worktrees": values }


@worktree.command ("path", cls=SortedCommand)
def path (
   name: Annotated [str, typer.Argument (help="Feature name, feature ID, or branch")] = "",
):
   """Print only a worktree's absolute path."""

   git.require ()
   try:
      feature = features.find (name) if name else features.resolve (
         states={ "active", "awaiting-merge" },
         title="Select worktree",
      )
   except state.StateError as error:
      console.fatal (str (error))
   if feature:
      if runtime.options.json:
         return result.emit (
            "imp.worktree-path.v1", "imp worktree path",
            { "feature_id": feature ["feature_id"], "name": feature ["name"], "path": feature ["path"] },
            json_output=True,
         )
      console.out.print (feature ["path"])
      return feature ["path"]
   branch_ref = f"refs/heads/{name}"
   for entry in git.worktrees ():
      if entry.get ("branch") == branch_ref or Path (entry.get ("worktree", "")).name == name:
         console.out.print (entry ["worktree"])
         return entry ["worktree"]
   console.fatal (f"No worktree for {name}")
   raise AssertionError ("unreachable")


def _show_remove (plan: dict):
   rows = [
      [ str (item ["action"]), str (item.get ("path") or item.get ("branch") or "claim") ]
      for item in plan ["items"]
   ]
   console.table (
      [ "Action", "Target" ],
      rows,
   )
   for blocker in plan ["blockers"]:
      console.err (str (blocker))


@worktree.command ("remove", cls=SortedCommand)
def remove (
   name: Annotated [str, typer.Argument (help="Managed feature name or ID")] = "",
   delete_branch: Annotated [bool, typer.Option ("--delete-branch", "-d", help="Delete a merged branch too")] = False,
   unmanaged: Annotated [bool, typer.Option ("--unmanaged", help="Remove a worktree with no feature record")] = False,
):
   """Remove one clean worktree. Managed worktrees go through an exact plan."""

   actor_id = runtime.options.actor_id
   yes = runtime.options.yes

   actor = identity.actor (actor_id)
   if unmanaged:
      return _remove_unmanaged (name, delete_branch, yes)
   try:
      feature = features.resolve (
         name,
         states={ "active", "awaiting-merge" },
         title="Select worktree to remove",
      )
      plan = features.plan_remove (feature, actor_id=actor, delete_branch=delete_branch)
   except state.StateError as error:
      console.fatal (str (error))
   _show_remove (plan)
   if runtime.options.dry_run:
      return plan
   if plan ["state"] != "ready":
      console.fatal ("Worktree removal plan is blocked")
   if runtime.options.no_input and not yes:
      console.fatal ("Non-interactive worktree removal requires --yes")
   console.confirm_or_exit ("Remove this clean worktree?", yes)
   try:
      data = features.apply_remove (plan, actor)
   except state.StateError as error:
      console.fatal (str (error))
   console.success (f"Removed {data ['path']}")
   return data


def _remove_unmanaged (name: str, delete_branch: bool, yes: bool):
   git.require ()
   if not name:
      console.fatal ("Worktree path, branch, or directory name is required")
   resolved = str (Path (name).expanduser ().resolve ())
   entry = next (
      (
         value for value in git.worktrees ()
         if str (Path (value.get ("worktree", "")).resolve ()) == resolved
         or value.get ("branch", "").removeprefix ("refs/heads/") == name
         or Path (value.get ("worktree", "")).name == name
      ),
      None,
   )
   if not entry:
      console.fatal (f"No worktree for {name}")
   path = str (Path (entry ["worktree"]).resolve ())
   managed = { str (Path (str (feature ["path"])).resolve ()) for feature in features.all () }
   if path in managed:
      console.fatal ("Worktree is managed; run imp worktree remove without --unmanaged")
   if not git.clean_at (path):
      console.fatal (f"Worktree has uncommitted changes: {path}")
   if runtime.options.no_input and not yes:
      console.fatal ("Non-interactive worktree removal requires --yes")
   if not yes and not console.confirm ("Remove this clean worktree?"):
      raise typer.Exit (0)
   branch = entry.get ("branch", "").removeprefix ("refs/heads/")
   git.worktree_remove (path)
   if delete_branch and branch and not git.delete_branch (branch):
      console.fatal (f"Branch is not merged; resolve it explicitly: {branch}")
   data = { "branch": branch, "path": path, "unmanaged": True }
   if runtime.options.json:
      result.emit ("imp.worktree.v1", "imp worktree remove", data, json_output=True)
   else:
      console.success (f"Removed {path}")
   return data


@worktree.command ("prune", cls=SortedCommand)
def prune (
   adopt: Annotated [
      bool,
      typer.Option ("--adopt", help="Record orphaned managed branches and worktrees as features"),
   ] = False,
   remove_orphans: Annotated [bool, typer.Option ("--remove", help="Delete clean orphaned worktrees")] = False,
):
   """Prune stale Git entries and reconcile managed worktree records."""

   actor_id = runtime.options.actor_id

   git.require ()
   if adopt and remove_orphans:
      console.fatal ("--adopt and --remove are mutually exclusive")
   git.worktree_prune ()
   missing = [feature for feature in features.all () if feature ["worktree_state"] == "missing"]
   for feature in missing:
      console.warn (f"Retained missing feature record: {feature ['name']}")
   found = features.orphans ()
   adopted = []
   removed = []
   for orphan in found:
      label = orphan ["path"] or orphan ["branch"]
      if adopt:
         try:
            adopted.append (str (features.adopt (orphan, identity.actor (actor_id)) ["feature_id"]))
            console.success (f"Adopted orphaned {orphan ['kind']}: {label}")
         except state.StateError as error:
            console.err (str (error))
         continue
      if remove_orphans:
         try:
            features.discard (orphan)
            removed.append (label)
            console.success (f"Removed orphaned {orphan ['kind']}: {label}")
         except state.StateError as error:
            console.err (str (error))
         continue
      console.warn (f"Orphaned managed {orphan ['kind']}: {label} (rerun with --adopt or --remove)")
   console.success ("Reconciled worktree records")
   return {
      "adopted": adopted,
      "missing_features": [feature ["feature_id"] for feature in missing],
      "orphans": found,
      "removed": removed,
   }


def _feature (name: str) -> dict:
   try:
      return features.resolve (name, title="Select feature")
   except state.StateError as error:
      console.fatal (str (error))


@worktree.command ("claim", cls=SortedCommand)
def claim_ (
   name: Annotated [str, typer.Argument (help="Feature name or ID")] = "",
   ttl: Annotated [str, typer.Option ("--ttl", help="Claim duration, such as 2h")] = "",
):
   """Acquire an unclaimed feature or renew the caller's claim."""

   actor_id = runtime.options.actor_id

   try:
      feature = _feature (name)
      value = features.claim (feature, identity.actor (actor_id), ttl)
   except state.StateError as error:
      console.fatal (str (error))
   console.success (f"Claimed {feature ['name']} until {value ['expires_at']}")
   return value


@worktree.command ("release", cls=SortedCommand)
def release_ (
   name: Annotated [str, typer.Argument (help="Feature name or ID")] = "",
):
   """Release the caller's writer claim without removing the worktree."""

   actor_id = runtime.options.actor_id

   try:
      feature = _feature (name)
      features.release (feature, identity.actor (actor_id))
   except state.StateError as error:
      console.fatal (str (error))
   console.success (f"Released {feature ['name']}")
