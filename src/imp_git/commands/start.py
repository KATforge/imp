from typing import Annotated

import typer

from imp_git import console, features, identity, plans, result, runtime, state


def _show (plan: dict):
   payload = plan ["payload"]
   console.header ("Start feature")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Feature", str (payload ["name"]) ],
         [ "Branch", str (payload ["branch"]) ],
         [ "Base", f"{payload ['base:ref']} ({str (payload ['base:oid']) [:10]})" ],
         [ "Worktree", str (payload ["path"]) ],
         [ "Writer", str (payload ["created_by"]) ],
      ],
   )


def start (
   name: Annotated [str, typer.Argument (help="Readable feature or lane name")] = "",
   task: Annotated [str, typer.Option ("--task", help="Optional working intent, not the prompt")] = "",
   branch: Annotated [str, typer.Option ("--branch", help="Explicit branch name")] = "",
   base: Annotated [str, typer.Option ("--base", help="Explicit base ref")] = "",
   target: Annotated [str, typer.Option ("--target", help="Integration target branch")] = "",
   path: Annotated [str, typer.Option ("--path", help="Explicit worktree path")] = "",
   change_id: Annotated [str, typer.Option ("--change-id", help="Temper change identity")] = "",
   use: Annotated [bool, typer.Option ("--use", help="Select this feature for local tools")] = False,
   no_claim: Annotated [bool, typer.Option ("--no-claim", help="Create without assigning a writer")] = False,
   plan_only: Annotated [bool, typer.Option ("--plan", help="Persist the plan without applying it")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply one saved plan")] = "",
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the exact displayed plan")] = False,
   dry_run: Annotated [bool, typer.Option ("--dry-run", help="Display an ephemeral plan")] = False,
   no_input: Annotated [bool, typer.Option ("--no-input", help="Fail instead of prompting")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit a versioned JSON result")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Create and claim an isolated feature worktree."""

   yes = yes or runtime.options.yes
   dry_run = dry_run or runtime.options.dry_run
   no_input = no_input or runtime.options.no_input
   try:
      if apply:
         plan = plans.resolve ("start", "" if apply == "__pick__" else apply)
      else:
         if not name:
            raise state.StateError ("Feature name is required")
         plan = features.plan_start (
            name,
            actor_id=identity.actor (actor_id),
            base=base,
            branch=branch,
            change_id=change_id,
            path=path,
            task=task,
            target=target,
            use=use,
            claim_writer=not no_claim,
            persist=not dry_run,
         )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   machine = json_output or runtime.options.json
   if not machine:
      _show (plan)

   if plan_only or dry_run:
      if machine:
         result.emit ("imp.start-plan.v1", "imp start", { "plan": plan }, json_output=True)
      else:
         console.hint ("Plan saved; apply it with imp start <name> --apply <plan-id>")
      return plan
   if no_input and not yes:
      console.fatal ("Non-interactive start requires --plan or --apply <plan-id> --yes")
   if not yes and not console.confirm ("Create this feature?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   try:
      feature = features.apply_start (plan)
   except state.StateError as error:
      console.fatal (str (error))

   if machine:
      result.emit ("imp.start.v1", "imp start", { "feature": feature }, json_output=True)
   else:
      console.success (f"Feature ready: {feature ['name']}")
      console.hint (f"cd {feature ['path']}")
   return feature
