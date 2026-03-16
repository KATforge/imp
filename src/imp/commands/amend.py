import typer

from imp import ai, console, git, prompts


def amend ():
   """Amend last commit with a new AI-generated message."""

   git.require ()

   console.header ("Amend")

   total = git.commit_count ()
   if total == 0:
      console.err ("No commits to amend")
      console.hint ("imp commit first")
      raise typer.Exit (1)

   last_msg = git.show ("HEAD", format="%s")

   if total == 1:
      combined = git.show ("HEAD")
      changes = git.diff ()
      if changes:
         combined = combined + "\n" + changes
   else:
      combined = git.diff_range ("HEAD~1")

   if not combined:
      console.err ("Nothing to amend")
      raise typer.Exit (1)

   msg = ai.commit_message (prompts.commit (combined))

   console.label ("Previous")
   console.item (last_msg)
   console.out.print ()

   git.stage (all=True)

   choice = console.review (msg)

   if choice == "Edit":
      git.commit (msg, edit=True, amend=True)
   elif choice == "Yes":
      git.commit (msg, amend=True)
   else:
      console.muted ("Cancelled")
      raise typer.Exit (0)

   console.success ("Amended")
   console.hint ("imp commit again, or imp release when ready")
