import typer

from imp_git import console, git


def undo (
   count: int = typer.Argument (1, help="Number of commits to undo"),
):
   """Undo last N commits, keeping changes staged.

   Soft-resets HEAD back by N commits so the changes remain staged and
   ready to recommit. Warns if any of the commits have already been
   pushed to the remote.
   """

   git.require ()

   console.header ("Undo")

   total = git.commit_count ()

   if count < 1:
      console.fatal ("Count must be at least 1")
   if total == 0:
      console.muted ("No commits to undo")
      raise typer.Exit (0)
   if count >= total:
      available = total - 1
      console.fatal (f"Only {available} commit(s) can be undone without removing the initial commit")

   log = git.log_oneline (count=count)
   console.items ("Commits to undo", log)
   console.out.print ()

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
