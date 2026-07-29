import typer

from imp import ai, console, git, prompts, workflow
from imp.commands.split import do_split

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
      console.hint ("git remote add origin <url>")
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
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Commit any changes, then push to origin.

   Stages everything, splits into logical commits if needed (or a single
   commit), rebases onto upstream if it moved, then pushes. Conflicts are
   named up front with the option to resolve them automatically. Does not
   create tags, changelogs, or releases.
   """

   git.require ()

   console.header ("Push")

   git.stage ()
   files = git.diff_names ()

   if files:
      did_split = False

      if len (files) >= 2:
         did_split = do_split (files, whisper, yes=True) is not None

      if not did_split:
         d = git.diff (staged=True)
         b = git.branch ()
         msg = ai.commit_message (prompts.commit (d, b, whisper))
         console.item (msg)
         git.commit (msg)
         console.success ("Committed")

      console.out.print ()

   do_push (pull=not no_pull)
