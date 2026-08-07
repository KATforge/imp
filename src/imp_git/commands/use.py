from typing import Annotated

import typer

from imp_git import console, features, result, runtime, state


def use (
   name: Annotated [str, typer.Argument (help="Feature name, feature ID, or trunk")] = "",
   json_output: Annotated [bool, typer.Option ("--json", help="Emit a versioned JSON result")] = False,
):
   """Select the source local viewers and test launchers should use."""

   try:
      if not name:
         candidates = features.eligible ({ "active", "awaiting-merge" })
         if runtime.options.json or runtime.options.no_input:
            console.fatal ("Feature name is required with --json or --no-input")
         labels = [ features.label (feature) for feature in candidates ]
         selected = console.choose ("Select active source", [ *labels, "trunk" ])
         name = candidates [labels.index (selected)] ["name"] if selected != "trunk" else "trunk"

      feature = None if name == "trunk" else features.resolve (
         name,
         states={ "active", "awaiting-merge" },
      )
      selection = features.select (feature)
   except state.StateError as error:
      console.fatal (str (error))

   if json_output or runtime.options.json:
      result.emit ("imp.use.v1", "imp use", selection, json_output=True)
   else:
      console.success (f"Active source: {name}")
      console.muted (str (selection ["path"]))

   return selection
