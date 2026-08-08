from typing import Annotated

import typer

from imp_git import console, result, runtime, state


def recover (
   operation: Annotated [str, typer.Argument (help="Recovery record ID")] = "",
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
):
   """Inspect Imp recovery records. It is not a Git reset alias."""

   directory = state.root () / "recovery"
   records = []
   if directory.exists ():
      for path in directory.glob ("*.json"):
         try:
            records.append (state.read (path, "imp.recovery.v1"))
         except state.StateError:
            continue
   if operation:
      records = [record for record in records if record.get ("recovery_id") == operation]
   data = { "recoveries": records }
   if json_output or runtime.options.json:
      return result.emit ("imp.recoveries.v1", "imp recover", data, json_output=True)
   if not records:
      console.muted ("No interrupted Imp operations")
      return data
   console.table (
      [ "Command", "Plan", "Error", "Next" ],
      [
         [
            str (record.get ("command", "")),
            str (record.get ("plan_id", "")),
            str (record.get ("error", "")),
            str (record.get ("next", "")),
         ]
         for record in records
      ],
   )
   return data
