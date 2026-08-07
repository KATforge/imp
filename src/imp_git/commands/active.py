from typing import Annotated

import typer

from imp_git import console, features, result, runtime, state


def active (
   path_only: Annotated [bool, typer.Option ("--path", help="Print only the absolute path")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit a versioned JSON result")] = False,
):
   """Read the active local source selection."""

   try:
      value = features.active ()
   except state.StateError as error:
      console.fatal (str (error))

   data = {
      "feature_id": value.get ("feature_id"),
      "generation": value ["generation"],
      "path": value ["path"],
   }
   if path_only:
      console.out.print (data ["path"])
   elif json_output or runtime.options.json:
      result.emit ("imp.active.v1", "imp active", data, json_output=True)
   else:
      console.header ("Active source")
      console.table (
         [ "Field", "Value" ],
         [
            [ "Feature", str (data ["feature_id"] or "trunk") ],
            [ "Path", str (data ["path"]) ],
            [ "Generation", str (data ["generation"]) ],
         ],
      )

   return data
