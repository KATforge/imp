from pathlib import Path
from typing import Annotated

import typer

from imp_git import console, features, git, identity, plans, result, runtime, state

worktree = typer.Typer (
   name="worktree",
   help="Inspect and manage linked worktrees",
   no_args_is_help=True,
)


@worktree.command ("list")
def list_ (
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
):
   """List repository worktrees and their managed feature state."""

   git.require ()
   selected = features.selection ()
   managed = { str (Path (feature ["path"]).resolve ()): feature for feature in features.all () }
   rows = []
   values = []
   for entry in git.worktrees ():
      path = str (Path (entry.get ("worktree", "")).resolve ())
      feature = managed.get (path)
      value = {
         "active": path == selected ["path"],
         "branch": entry.get ("branch", "").removeprefix ("refs/heads/"),
         "feature_id": feature.get ("feature_id") if feature else None,
         "name": feature.get ("name") if feature else ("trunk" if not values else "unmanaged"),
         "path": path,
         "state": feature.get ("worktree_state", "live") if feature else "unmanaged",
         "target": feature.get ("target") if feature else None,
      }
      values.append (value)
      rows.append ([ "*" if value ["active"] else "", str (value ["name"]), value ["branch"], path, value ["state"] ])
   if json_output or runtime.options.json:
      return result.emit ("imp.worktrees.v1", "imp worktree list", { "worktrees": values }, json_output=True)
   console.table ([ "Active", "Feature", "Branch", "Path", "State" ], rows)
   return { "worktrees": values }


@worktree.command ("path")
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


@worktree.command ("remove")
def remove (
   name: Annotated [str, typer.Argument (help="Managed feature name or ID")] = "",
   delete_branch: Annotated [bool, typer.Option ("--delete-branch", "-d", help="Delete a merged branch too")] = False,
   plan_only: Annotated [bool, typer.Option ("--plan", help="Persist without applying")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply a saved plan")] = "",
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the displayed plan")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Remove one clean managed worktree through an exact plan."""

   actor = identity.actor (actor_id)
   yes = yes or runtime.options.yes
   try:
      if apply:
         plan = plans.resolve ("worktree-remove", "" if apply == "__pick__" else apply)
      else:
         feature = features.resolve (
            name,
            states={ "active", "awaiting-merge" },
            title="Select worktree to remove",
         )
         plan = features.plan_remove (
            feature,
            actor_id=actor,
            delete_branch=delete_branch,
            persist=not runtime.options.dry_run,
         )
   except state.StateError as error:
      console.fatal (str (error))
   _show_remove (plan)
   if plan_only or runtime.options.dry_run:
      return plan
   if plan ["state"] != "ready":
      console.fatal ("Worktree removal plan is blocked")
   if runtime.options.no_input and not yes:
      console.fatal ("Non-interactive worktree removal requires --apply <plan-id> --yes")
   console.confirm_or_exit ("Remove this clean worktree?", yes)
   try:
      data = features.apply_remove (plan, actor)
   except state.StateError as error:
      console.fatal (str (error))
   console.success (f"Removed {data ['path']}")
   return data


@worktree.command ("prune")
def prune ():
   """Prune stale Git entries and report retained missing feature records."""

   git.require ()
   git.worktree_prune ()
   missing = [feature for feature in features.all () if feature ["worktree_state"] == "missing"]
   for feature in missing:
      console.warn (f"Retained missing feature record: {feature ['name']}")
   console.success ("Reconciled worktree records")
   return { "missing_features": [feature ["feature_id"] for feature in missing] }


def _feature (name: str) -> dict:
   try:
      return features.resolve (name, title="Select feature")
   except state.StateError as error:
      console.fatal (str (error))


@worktree.command ("claim")
def claim_ (
   name: Annotated [str, typer.Argument (help="Feature name or ID")] = "",
   ttl: Annotated [str, typer.Option ("--ttl", help="Claim duration, such as 2h")] = "",
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Acquire an unclaimed feature or renew the caller's claim."""

   try:
      feature = _feature (name)
      value = features.claim (feature, identity.actor (actor_id), ttl)
   except state.StateError as error:
      console.fatal (str (error))
   console.success (f"Claimed {feature ['name']} until {value ['expires_at']}")
   return value


@worktree.command ("release")
def release_ (
   name: Annotated [str, typer.Argument (help="Feature name or ID")] = "",
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Release the caller's writer claim without removing the worktree."""

   try:
      feature = _feature (name)
      features.release (feature, identity.actor (actor_id))
   except state.StateError as error:
      console.fatal (str (error))
   console.success (f"Released {feature ['name']}")
