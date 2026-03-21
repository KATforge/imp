import typer

from imp import ai, console, git, prompts


def revert (
   ref: str | None = typer.Argument (None, help="Commit hash to revert"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Safely revert a pushed commit.

   Pass a commit hash, or omit it to pick from the last 10 commits
   interactively. Shows the changes that will be undone, then uses AI to
   generate a revert commit message that you can review or edit before
   committing.
   """

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

   commit_msg = git.show (ref, fmt="%s")
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

   msg = ai.fast (prompts.revert (commit_msg, d, whisper))
   msg = ai.oneline (msg)

   git.revert_commit (ref, no_commit=True)

   choice = console.review (msg)

   if choice == "Edit":
      msg = console.edit (msg)
      if not msg.strip ():
         git.revert_abort ()
         console.muted ("Empty message, cancelled")
         raise typer.Exit (0)
      git.commit (msg)
   elif choice == "Yes":
      git.commit (msg)
   else:
      git.revert_abort ()
      console.muted ("Cancelled")
      raise typer.Exit (0)

   console.success (f"Reverted {commit_hash}")
   console.hint ("imp sync to push, or imp undo to cancel")
