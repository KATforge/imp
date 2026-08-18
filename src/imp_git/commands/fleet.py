from typing import Annotated

import typer

from imp_git import approval, console, git, identity, runtime, state
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
):
   """Consolidate every managed feature in one repository."""

   git.require ()

   actor_id = runtime.options.actor_id
   dry_run = runtime.options.dry_run
   json_output = runtime.options.json
   yes = runtime.options.yes

   actor = identity.actor (actor_id)
   try:
         plan = fleet_mod.plan_fleet (
            actor_id=actor,
            into=into,
            strategy=strategy,
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
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
      plan_hint="Review blocked members with imp review <feature>, then apply this fleet plan.",
   )
