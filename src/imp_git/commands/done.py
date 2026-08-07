from typing import Annotated

import typer

from imp_git import console, features, identity, integration, plans, result, runtime, state


def _feature (value: str) -> dict:
   return features.resolve (
      value,
      states={ "active", "awaiting-merge" },
      title="Select feature to complete",
   )


def _show (plan: dict):
   payload = plan ["payload"]
   console.header ("Complete feature")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Feature", str (plan ["label"]) ],
         [ "Target", str (payload ["target_ref"]) ],
         [ "Strategy", str (payload ["strategy"]) ],
         [ "Candidate", str (payload ["candidate_oid"]) [:12] ],
         [ "Mode", "pull request" if payload ["pr"] else "direct" ],
      ],
   )
   for blocker in plan.get ("blockers", []):
      console.err (str (blocker))


def done (
   feature: Annotated [str, typer.Argument (help="Feature name")] = "",
   into: Annotated [str, typer.Option ("--into", help="Integration target")] = "",
   strategy: Annotated [str, typer.Option ("--strategy", help="preserve, squash, or merge")] = "",
   pr: Annotated [bool, typer.Option ("--pr", help="Push the feature and open a pull request")] = False,
   push: Annotated [bool, typer.Option ("--push", help="Push the integrated target")] = False,
   keep: Annotated [bool, typer.Option ("--keep", help="Keep the feature worktree and branch")] = False,
   skip_checks: Annotated [bool, typer.Option ("--skip-checks", help="Explicitly bypass checks")] = False,
   plan_only: Annotated [bool, typer.Option ("--plan", help="Prepare the exact candidate only")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply one saved plan")] = "",
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the displayed plan")] = False,
   dry_run: Annotated [bool, typer.Option ("--dry-run", help="Display an ephemeral plan")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Validate and integrate exactly one managed feature."""

   actor = identity.actor (actor_id)
   yes = yes or runtime.options.yes
   dry_run = dry_run or runtime.options.dry_run
   try:
      if apply:
         plan = plans.resolve ("done", "" if apply == "__pick__" else apply)
      else:
         selected = _feature (feature)
         reusable = (
            None
            if any ([ into, keep, pr, push, skip_checks, strategy, dry_run ])
            else integration.reusable_plan (selected)
         )
         plan = reusable or integration.plan_done (
            selected, actor_id=actor, into=into, keep=keep, pr=pr,
            push=push, skip_checks=skip_checks, strategy=strategy, persist=not dry_run,
         )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   machine = json_output or runtime.options.json
   if not machine:
      _show (plan)
   if plan_only or dry_run:
      if machine:
         result.emit ("imp.done-plan.v1", "imp done", { "plan": plan }, json_output=True)
      return plan
   if plan.get ("state") != "ready":
      console.fatal ("Integration plan is blocked")
   if runtime.options.no_input and not yes:
      console.fatal ("Non-interactive completion requires --plan or --apply <plan-id> --yes")
   if not yes and not console.confirm ("Apply this exact integration plan?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)
   try:
      data = integration.apply_done (plan, actor)
   except state.StateError as error:
      console.fatal (str (error))
   if machine:
      result.emit ("imp.done.v1", "imp done", data, json_output=True)
   else:
      console.success ("Feature completed")
   return data
