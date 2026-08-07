from typing import Annotated

import typer

from imp_git.commands.commit import commit


def split (
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the exact displayed plan")] = False,
   whisper: Annotated [str, typer.Option ("--whisper", "-w", help="Context for commit planning")] = "",
   plan_only: Annotated [bool, typer.Option ("--plan", help="Persist the plan without applying it")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply one saved commit plan")] = "",
   dry_run: Annotated [bool, typer.Option ("--dry-run", help="Display an ephemeral plan")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit a versioned JSON result")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Alias for `imp commit --all`."""

   return commit (
      all=True,
      exclude=None,
      yes=yes,
      push=False,
      whisper=whisper,
      message="",
      staged=False,
      single=False,
      plan_only=plan_only,
      apply=apply,
      list_plans=False,
      dry_run=dry_run,
      json_output=json_output,
      actor_id=actor_id,
      amend=False,
      fixup="",
   )
