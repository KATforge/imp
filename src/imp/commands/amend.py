import typer

from imp import ai, console, git, prompts, workflow
from imp.commands import push as push_cmd

def amend (
   yes: bool = typer.Option (False, "--yes", "-y", help="Accept AI message without review"),
   push: bool = typer.Option (False, "--push", "-p", help="Force-push (with lease) after amending"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Amend last commit with a new AI-generated message.

   Stages any uncommitted changes, regenerates the commit message from the
   full diff, and amends the previous commit. You can review, edit, or
   cancel the new message before it's applied. Use --push/-p to force-push
   (with lease) afterwards.
   """

   git.require ()

   total = git.commit_count ()
   if total == 0:
      console.hint ("imp commit first")
      console.fatal ("No commits to amend")

   console.header ("Amend")

   last_msg = git.show ("HEAD", fmt="%s")

   combined = git.show ("HEAD")
   changes = git.diff ()
   if changes:
      combined = combined + "\n" + changes

   if not combined:
      console.fatal ("Nothing to amend")

   msg = ai.commit_message (prompts.commit (combined, whisper=whisper))

   console.label ("Previous")
   console.item (last_msg)
   console.out.print ()

   git.stage ()

   workflow.review_commit (msg, yes, amend=True)

   console.success ("Amended")

   if push:
      console.out.print ()
      push_cmd.do_push (force_lease=True)
      return

   console.hint ("imp commit again, or imp release when ready")
