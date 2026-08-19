from collections.abc import Callable
from typing import Any

import typer

from imp_git import console, identity, result, runtime, state


def _approved (noun: str, confirm: str, destructive: bool) -> bool:
   """Decide whether the shown candidate may be applied.

   Agents approve their own reversible work, so routine start/commit/done runs
   never stall on a prompt. Anything destructive or outward-facing still needs
   a person: an explicit --yes, or an interactive confirmation.
   """

   options = runtime.options
   if options.yes:
      return True
   if not destructive and identity.is_agent ():
      return True
   if options.no_input:
      console.fatal (f"Non-interactive {noun} requires --yes")
   if not console.confirm (confirm):
      console.muted ("Cancelled")
      raise typer.Exit (0)
   return True


def run (
   plan: dict [str, Any],
   *,
   noun: str,
   confirm: str,
   result_schema: str,
   apply: Callable [[dict [str, Any]], dict [str, Any]],
   show: Callable [[dict [str, Any]], None],
   success: Callable [[dict [str, Any]], None],
   wrap: str = "",
   warnings: list [str] | None = None,
   destructive: bool = False,
) -> dict [str, Any]:
   """Display exactly what will happen, gate on approval, then do it.

   Every mutating command shares this spine so the approval contract cannot drift
   between them. The candidate is built and shown first, so `--dry-run` stops here
   and nothing outside the object database has changed. `wrap` nests the applied
   data under one key in the machine result.
   """

   options = runtime.options
   command = str (plan ["command"])
   notes = warnings or []
   if not options.json:
      show (plan)
      for note in notes:
         console.warn (note)
   if options.dry_run:
      if options.json:
         result.emit (str (plan ["payload_schema"]), command, { "plan": plan }, json_output=True, warnings=notes)
      return plan
   if plan.get ("state") != "ready":
      console.fatal (f"{noun.capitalize ()} is blocked")
   _approved (noun, confirm, destructive)
   try:
      data = apply (plan)
   except state.StateError as error:
      console.fatal (str (error))
   if options.json:
      result.emit (result_schema, command, { wrap: data } if wrap else data, json_output=True, warnings=notes)
   else:
      success (data)

   return data
