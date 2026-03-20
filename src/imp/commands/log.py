from typing import Optional

import typer

from imp import console, git


def log (
   count: int = typer.Option (20, "-n", help="Number of commits"),
   ref: Optional [str] = typer.Argument (None, help="Branch or commit ref"),
):
   """Show pretty commit graph.

   Displays a decorated commit graph with branch topology. Defaults to
   the last 20 commits; use -n to adjust. Optionally pass a branch or
   ref to view its history instead of the current branch.
   """

   git.require ()

   console.header ("Log")

   output = git.log_graph (count, ref or "")
   if output:
      print (output)
   else:
      console.muted ("No commits")
