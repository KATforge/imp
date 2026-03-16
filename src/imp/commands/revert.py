from typing import Optional

import typer

from imp import ai, console, git, prompts


def revert (
   ref: Optional [str] = typer.Argument (None, help="Commit hash to revert"),
):
   """Safely revert a pushed commit."""

   git.require ()

   console.header ("Revert")

   if not ref:
      log = git.log_oneline (count=10)
      if not log:
         console.muted ("No commits to revert")
         raise typer.Exit (0)

      lines = log.splitlines ()
      choice = console.choose ("Select commit to revert:", lines)
      ref = choice.split (" ", 1) [0]

   if not ref:
      console.muted ("Cancelled")
      raise typer.Exit (0)

   if not git.rev_parse (ref):
      console.err (f"Invalid commit: {ref}")
      raise typer.Exit (1)

   commit_msg = git.show (ref, format="%s")
   commit_hash = git.rev_parse_short (ref)

   console.label ("Reverting")
   console.item (f"{commit_hash} {commit_msg}")
   console.out.print ()

   stat = git.show (ref, stat=True)
   if stat:
      console.muted ("Changes to undo:")
      for line in stat.splitlines ():
         if line.strip ():
            console.item (line)
      console.out.print ()

   if not console.confirm ("Create revert commit?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   d = git.diff_range (f"{ref}~1..{ref}", max_lines=500)

   msg = ai.fast (prompts.revert (commit_msg, d))
   msg = ai.sanitize (msg)

   git.revert_commit (ref, no_commit=True)

   choice = console.review (msg)

   if choice == "Edit":
      git.commit (msg, edit=True)
   elif choice == "Yes":
      git.commit (msg)
   else:
      git.revert_abort ()
      console.muted ("Cancelled")
      raise typer.Exit (0)

   console.success (f"Reverted {commit_hash}")
   console.hint ("imp sync to push, or imp undo to cancel")
