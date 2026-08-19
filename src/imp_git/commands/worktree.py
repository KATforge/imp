from typing import Annotated

import typer

from imp_git import approval, console, features, identity, result, runtime, state
from imp_git.cli import SortedCommand

worktree = typer.Typer (name="worktree", help="Locate or discard feature worktrees", no_args_is_help=True)


@worktree.command ("path", cls=SortedCommand)
def path (
   name: Annotated [str, typer.Argument (help="Feature name")] = "",
):
   """Print a feature worktree path."""

   try:
      feature = features.resolve (name, states={ "active", "awaiting-merge" }, title="Select feature")
   except state.StateError as error:
      console.fatal (str (error))
   if runtime.options.json:
      return result.emit (
         "imp.worktree-path.v1", "imp worktree path",
         { "feature_id": feature ["feature_id"], "name": feature ["name"], "path": feature ["path"] },
         json_output=True,
      )
   console.out.print (feature ["path"])
   return feature ["path"]


def _show (plan: dict):
   console.header ("Discard feature")
   console.table ([ "Action", "Target" ], [
      [ str (item ["action"]), str (item.get ("path") or item.get ("branch") or item.get ("feature")) ]
      for item in plan ["items"]
   ])
   for blocker in plan ["blockers"]:
      console.err (str (blocker))


@worktree.command ("remove", cls=SortedCommand)
def remove (
   name: Annotated [str, typer.Argument (help="Feature name")] = "",
):
   """Discard one clean feature and its branch."""

   actor = identity.actor (runtime.options.actor_id)
   try:
      feature = features.resolve (name, states={ "active", "awaiting-merge" }, title="Select feature")
      plan = features.plan_remove (feature, actor_id=actor)
   except state.StateError as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      command="imp worktree remove",
      noun="discard",
      confirm="Discard this feature?",
      plan_schema="imp.remove-plan.v2",
      result_schema="imp.remove.v2",
      apply=lambda value: features.apply_remove (value, actor),
      show=_show,
      success=lambda data: console.success (f"Discarded {data ['feature_id']}"),
      dry_run=runtime.options.dry_run,
      yes=runtime.options.yes,
      json_output=runtime.options.json,
   )
