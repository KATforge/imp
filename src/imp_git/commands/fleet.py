from typing import Annotated

import typer

from imp_git import approval, console, identity, plans, runtime, state
from imp_git import fleet as fleet_mod


def _show (plan: dict):
   payload = plan ["payload"]
   console.header ("Repository fleet")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Repository", str (plan ["label"]) ],
         [ "Target", str (payload ["target_ref"]) ],
         [ "Mode", "pull requests" if payload ["mode"] == "pr" else "local integration" ],
         [ "Strategy", str (payload ["strategy"]) ],
         [ "Features", str (len (payload ["children"])) ],
      ],
   )
   if payload ["children"]:
      console.table (
         [ "Feature", "Branch", "Plan" ],
         [
            [ str (child ["name"]), str (child ["branch"]), str (child ["plan_id"]) ]
            for child in payload ["children"]
         ],
      )
   for blocker in plan.get ("blockers", []):
      console.err (str (blocker))


def fleet (
   into: Annotated [str, typer.Option ("--into", help="Integration target; defaults to repository trunk")] = "",
   strategy: Annotated [str, typer.Option ("--strategy", help="preserve, squash, or merge")] = "squash",
   pr: Annotated [bool, typer.Option ("--pr", help="Push every feature and open or update pull requests")] = False,
   plan_only: Annotated [bool, typer.Option ("--plan", help="Prepare the exact fleet only")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply one saved fleet plan")] = "",
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the displayed plan")] = False,
   dry_run: Annotated [bool, typer.Option ("--dry-run", help="Display an ephemeral plan")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Consolidate every managed feature in one repository."""

   actor = identity.actor (actor_id)
   yes = yes or runtime.options.yes
   dry_run = dry_run or runtime.options.dry_run
   try:
      if apply:
         plan = fleet_mod.refresh (plans.resolve ("fleet", "" if apply == "__pick__" else apply))
      else:
         plan = fleet_mod.plan_fleet (
            actor_id=actor,
            into=into,
            pr=pr,
            strategy=strategy,
            persist=not dry_run,
         )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      command="imp fleet",
      noun="fleet",
      confirm="Apply this exact repository fleet?",
      plan_schema="imp.fleet-plan.v1",
      result_schema="imp.fleet.v1",
      apply=lambda value: fleet_mod.apply_fleet (value, actor),
      show=_show,
      success=lambda data: console.success (f"Fleet completed on {data ['target']}"),
      plan_only=plan_only,
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
      plan_hint="Review blocked members with imp review <feature>, then apply this fleet plan.",
   )
