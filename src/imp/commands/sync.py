import typer

from imp import console, git


def sync ():
   """Pull, rebase, and push current branch."""

   git.require ()
   git.require_clean ("imp commit first")

   console.header ("Sync")

   b = git.branch ()

   if not git.has_upstream ():
      console.err ("No upstream branch")
      console.hint (f"git push -u origin {b}")
      raise typer.Exit (1)

   console.label ("Branch")
   console.item (b)
   console.out.print ()

   console.spin ("Fetching...", git.fetch)

   behind = git.count_behind ()
   ahead = git.count_ahead ()

   if behind == 0 and ahead == 0:
      console.success ("Already up to date")
      raise typer.Exit (0)

   if behind > 0:
      console.label ("Behind")
      console.item (f"{behind} commits")

   if ahead > 0:
      console.label ("Ahead")
      console.item (f"{ahead} commits")

   console.out.print ()

   if behind > 0:
      console.muted ("Rebasing...")
      if not git.rebase ():
         console.err ("Rebase failed")
         console.hint ("git rebase --abort to cancel")
         raise typer.Exit (1)
      console.success ("Rebased")

   if ahead > 0 or behind > 0:
      if console.confirm ("Push?"):
         git.push ()
         console.success ("Pushed")

   console.hint ("imp status to see overview")
