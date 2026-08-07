import typer

from imp_git import console, git, workflow


def do_push (force_lease: bool = False, pull: bool = True):
   """Push the current branch to origin.

   Checks for a remote, fetches, reconciles with upstream, counts ahead, sets
   upstream if needed. Returns silently if nothing to push. Pass
   force_lease=True to rewrite history safely (used after amend or rebase),
   pull=False to push without reconciling first.
   """

   b = git.branch ()

   if not git.remote_exists ():
      console.err ("No remote configured")
      console.hint ("imp remote add origin <url>")
      raise typer.Exit (1)

   if git.has_upstream ():
      if not pull:
         git.fetch ()
      elif not workflow.reconcile ():
         raise typer.Exit (1)

      if force_lease:
         console.item (f"Force-pushing {b}")
         git.push (force_lease=True)
      else:
         ahead = git.count_ahead ()

         if ahead == 0:
            console.success ("Nothing to push")
            return

         console.item (f"{ahead} commits on {b}")
         git.push ()
   else:
      console.item (f"Setting upstream for {b}")
      git.push (set_upstream=True, target=b)

   console.success ("Pushed to origin")

def push (
   no_pull: bool = typer.Option (False, "--no-pull", help="Push without reconciling with upstream first"),
):
   """Push existing commits to origin without committing dirty work."""

   git.require ()

   console.header ("Push")
   do_push (pull=not no_pull)
