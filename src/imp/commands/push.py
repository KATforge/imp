import typer

from imp import console, git


def do_push ():
   """Push the current branch to origin.

   Checks for a remote, fetches, counts ahead, sets upstream if needed.
   Returns silently if nothing to push.
   """

   b = git.branch ()

   if not git.remote_exists ():
      console.err ("No remote configured")
      console.hint ("git remote add origin <url>")
      raise typer.Exit (1)

   if git.has_upstream ():
      git.fetch ()
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


def push ():
   """Push commits to origin.

   Pushes the current branch. Sets upstream tracking on first push.
   Does not create tags, changelogs, or releases.
   """

   git.require ()
   git.require_clean ()

   console.header ("Push")

   do_push ()
