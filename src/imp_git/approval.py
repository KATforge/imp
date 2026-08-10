from collections.abc import Callable
from typing import Any

import typer

from imp_git import console, result, runtime, state


def run (
   plan: dict [str, Any],
   *,
   command: str,
   noun: str,
   confirm: str,
   plan_schema: str,
   result_schema: str,
   apply: Callable [[dict [str, Any]], dict [str, Any]],
   show: Callable [[dict [str, Any]], None],
   success: Callable [[dict [str, Any]], None],
   plan_only: bool,
   dry_run: bool,
   yes: bool,
   json_output: bool,
   no_input: bool = False,
   wrap: str = "",
) -> dict [str, Any]:
   """Display one exact plan, gate on explicit approval, apply it, and emit the result.

   Every plan-driven command shares this spine so the approval contract cannot
   drift between commands. `wrap` nests the applied data under one key in the
   machine result. A saved human-readable plan reports its own identity so the
   caller can apply exactly it; a `dry_run` plan is ephemeral and reports none.
   """

   machine = json_output or runtime.options.json
   if not machine:
      show (plan)
   if plan_only or dry_run:
      if machine:
         result.emit (plan_schema, command, { "plan": plan }, json_output=True)
      elif not dry_run:
         console.hint (f"Plan saved: {plan ['plan_id']}")
         console.muted (f"  {command} --apply {plan ['plan_id']} --yes")
      return plan
   if plan.get ("state") != "ready":
      console.fatal (f"{noun.capitalize ()} plan is blocked")
   if (no_input or runtime.options.no_input) and not yes:
      console.fatal (f"Non-interactive {noun} requires --plan or --apply <plan-id> --yes")
   if not yes and not console.confirm (confirm):
      console.muted ("Cancelled")
      raise typer.Exit (0)
   try:
      data = apply (plan)
   except state.StateError as error:
      console.fatal (str (error))
   if machine:
      result.emit (result_schema, command, { wrap: data } if wrap else data, json_output=True)
   else:
      success (data)
   return data
