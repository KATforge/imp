import sys
from typing import Annotated

import typer

from imp_git import approval, console, features, result, runtime, state
from imp_git.cli import SortedCommand

worktree = typer.Typer (name="worktree", help="Locate or discard feature worktrees", no_args_is_help=True)


@worktree.command ("path", cls=SortedCommand)
def path (
   name: Annotated [str, typer.Argument (help="Feature name or branch")] = "",
):
   """Print one feature's worktree path, for `cd $(imp worktree path <name>)`."""

   try:
      feature = features.resolve (name, live=True, title="Select feature")
   except state.StateError as error:
      console.fatal (str (error))
   if runtime.options.json:
      return result.emit (
         "imp.worktree-path.v2", "imp worktree path",
         { "branch": feature ["branch"], "name": feature ["name"], "path": feature ["path"] },
         json_output=True,
      )
   sys.stdout.write (feature ["path"] + "\n")
   return feature ["path"]


def _show (plan: dict):
   console.header ("Discard feature")
   console.table ([ "Action", "Target" ], [
      [ str (item ["action"]), str (item.get ("path") or item.get ("branch")) ]
      for item in plan ["items"]
   ])
   for blocker in plan ["blockers"]:
      console.err (str (blocker))


@worktree.command ("remove", cls=SortedCommand)
def remove (
   name: Annotated [str, typer.Argument (help="Feature name or branch")] = "",
):
   """Discard one clean feature: park its tip in the attic, then delete branch and worktree.

   Refuses a dirty worktree; commit or stash first, or let `imp cleanup` judge it. The
   branch tip stays under refs/imp/attic for 30 days, recoverable with
   `git branch <name> <attic-ref>`.
   """

   try:
      feature = features.resolve (name, title="Select feature")
      plan = features.plan_remove (feature)
   except state.StateError as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      noun="discard",
      confirm="Discard this feature?",
      result_schema="imp.remove.v3",
      apply=features.apply_remove,
      show=_show,
      success=lambda data: console.success (f"Discarded {data ['branch']} (attic: {data ['attic']})"),
      destructive=True,
   )
