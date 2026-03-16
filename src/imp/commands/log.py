from typing import Optional

import typer

from imp import console, git


def log (
   count: int = typer.Option (20, "-n", help="Number of commits"),
   ref: Optional [str] = typer.Argument (None, help="Branch or commit ref"),
):
   """Show pretty commit graph."""

   git.require ()

   console.header ("Log")

   output = git.log_graph (count, ref or "")
   if output:
      print (output)
   else:
      console.muted ("No commits")
