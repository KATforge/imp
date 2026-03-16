from typing import Optional

import typer

from imp import console, git


def undo (
   count: Optional [int] = typer.Argument (1, help="Number of commits to undo"),
):
   """Undo last N commits, keeping changes staged."""

   git.require ()

   console.header ("Undo")

   if git.commit_count () == 0:
      console.muted ("No commits to undo")
      raise typer.Exit (0)

   total = git.commit_count ()
   if count > total:
      console.err (f"Only {total} commits available")
      raise typer.Exit (1)

   log = git.log_oneline (count=count)
   console.items ("Commits to undo", log)

   if git.has_upstream ():
      ahead = git.count_ahead ()
      if count > ahead:
         console.warn ("Some commits are already pushed")
         console.out.print ()

   if not console.confirm (f"Undo {count} commit(s)? (changes stay staged)"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   git.reset (f"HEAD~{count}", soft=True)

   console.success (f"Undone {count} commit(s)")
   console.hint ("imp commit to recommit, or keep editing")
