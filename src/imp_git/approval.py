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
   dry_run: bool,
   yes: bool,
   json_output: bool,
   wrap: str = "",
) -> dict [str, Any]:
   """Display exactly what will happen, gate on approval, then do it.

   Every mutating command shares this spine so the approval contract cannot drift
   between them. The candidate is built and shown first, so `--dry-run` stops here
   and nothing outside the object database has changed. `wrap` nests the applied
   data under one key in the machine result.
   """

   machine = json_output or runtime.options.json
   if not machine:
      show (plan)
   if dry_run:
      if machine:
         result.emit (plan_schema, command, { "plan": plan }, json_output=True)
      return plan
   if plan.get ("state") != "ready":
      console.fatal (f"{noun.capitalize ()} is blocked")
   if runtime.options.no_input and not yes:
      console.fatal (f"Non-interactive {noun} requires --yes")
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
