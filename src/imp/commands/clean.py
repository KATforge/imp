import typer

from imp import console, git

def clean ():
   """Delete branches already merged into base.

   Fetches from origin, finds local branches fully merged into the base
   branch (main/master), and deletes them locally and remotely. Prompts
   for confirmation before deleting.
   """

   git.require ()

   console.header ("Clean")

   base = git.base_branch ()

   console.spin ("Fetching...", git.fetch, True)

   merged = git.branches_merged (base)

   if not merged:
      console.success ("No merged branches to clean")
      raise typer.Exit (0)

   console.label (f"Merged into {base}")
   for b in merged:
      console.item (b)
   console.out.print ()

   count = len (merged)
   if not console.confirm (f"Delete {count} branch(es)?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   console.out.print ()
   for b in merged:
      git.delete_branch (b)
      console.success (f"Deleted {b}")

      if git.remote_has_branch (b):
         git.delete_branch (b, remote=True)
         console.success (f"Deleted remote {b}")

   console.hint ("imp branch to start something new")
