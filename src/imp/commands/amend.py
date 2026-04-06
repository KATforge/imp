import typer

from imp import ai, console, git, prompts, workflow


def amend (
   yes: bool = typer.Option (False, "--yes", "-y", help="Accept AI message without review"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Amend last commit with a new AI-generated message.

   Stages any uncommitted changes, regenerates the commit message from the
   full diff, and amends the previous commit. You can review, edit, or
   cancel the new message before it's applied.
   """

   git.require ()

   console.header ("Amend")

   total = git.commit_count ()
   if total == 0:
      console.hint ("imp commit first")
      console.fatal ("No commits to amend")

   last_msg = git.show ("HEAD", fmt="%s")

   if total == 1:
      combined = git.show ("HEAD")
      changes = git.diff ()
      if changes:
         combined = combined + "\n" + changes
   else:
      combined = git.diff_range ("HEAD~1")

   if not combined:
      console.fatal ("Nothing to amend")

   msg = ai.commit_message (prompts.commit (combined, whisper=whisper))

   console.label ("Previous")
   console.item (last_msg)
   console.out.print ()

   git.stage ()

   workflow.review_commit (msg, yes, amend=True)

   console.success ("Amended")
   console.hint ("imp commit again, or imp release when ready")
