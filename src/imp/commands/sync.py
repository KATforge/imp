import typer

from imp import console, git

def sync (
   yes: bool = typer.Option (False, "--yes", "-y", help="Push without confirmation"),
):
   """Pull, rebase, and push current branch.

   Fetches from origin, rebases local commits on top of upstream changes,
   and offers to push. Requires a clean working tree and an upstream
   tracking branch. Aborts cleanly if the rebase fails.
   """

   git.require ()
   git.require_clean ("imp commit first")

   console.header ("Sync")

   b = git.branch ()

   if not git.has_upstream ():
      console.hint (f"git push -u origin {b}")
      console.fatal ("No upstream branch")

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
      console.out.print ()

   if ahead > 0:
      console.label ("Ahead")
      console.item (f"{ahead} commits")
      console.out.print ()

   if behind > 0:
      console.muted ("Rebasing...")
      if not git.rebase ():
         console.hint ("imp resolve to fix conflicts, or git rebase --abort")
         console.fatal ("Rebase failed")
      console.success ("Rebased")

   if ahead > 0 or behind > 0:
      if yes or console.confirm ("Push?"):
         git.push ()
         console.success ("Pushed")

   console.hint ("imp status to see overview")
