import typer

from imp import console, git


def done ():
   """Clean up after PR merge: switch to base, delete branch."""

   git.require ()

   console.header ("Done")

   b = git.branch ()
   base = git.base_branch ()

   if b == base:
      console.err (f"Already on {base}")
      console.hint ("switch to a feature branch first")
      raise typer.Exit (1)

   git.require_clean ()

   console.label ("Switching")
   console.item (f"{b} → {base}")
   console.out.print ()

   git.checkout (base)

   if git.has_upstream ():
      git.pull ()

   if git.delete_branch (b):
      console.success (f"Deleted local branch {b}")
   else:
      console.warn (f"Branch {b} has unmerged changes")
      console.out.print ()
      if console.confirm (f"Force delete {b}?"):
         git.delete_branch (b, force=True)
         console.success (f"Force deleted local branch {b}")
      else:
         console.muted (f"Kept local branch {b}")

   if git.remote_has_branch (b):
      git.delete_branch (b, remote=True)
      console.success (f"Deleted remote branch {b}")

   console.hint ("imp branch to start something new")
