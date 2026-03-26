from fnmatch import fnmatch
from typing import Optional

import typer

from imp import ai, console, git, prompts


def commit (
   all: bool = typer.Option (False, "--all", "-a", help="Stage all changes first"),
   exclude: Optional [list [str]] = typer.Option (None, "--exclude", "-E", help="Glob patterns to exclude from staging"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Generate an AI commit message for staged changes.

   Reads the staged diff and uses AI to produce a Conventional Commits
   message. Use --all/-a to stage everything first. You can review, edit,
   or cancel the message before committing.
   """

   git.require ()

   if all:
      git.stage (all=True)

   if exclude:
      staged = git.staged_files ()
      to_unstage = [
         f for f in staged
         if any (fnmatch (f, pat) for pat in exclude)
      ]
      if to_unstage:
         git.unstage (to_unstage)
         console.muted (f"Excluded {len (to_unstage)} files")

   d = git.diff (staged=True)
   if not d:
      console.err ("Nothing staged")
      console.hint ("git add <files>, or imp commit -a")
      raise typer.Exit (1)

   console.header ("Commit")

   b = git.branch ()
   msg = ai.commit_message (prompts.commit (d, b, whisper))

   choice = console.review (msg)

   if choice == "Edit":
      msg = console.edit (msg)
      if not msg.strip ():
         console.muted ("Empty message, cancelled")
         raise typer.Exit (0)
      git.commit (msg)
   elif choice == "Yes":
      git.commit (msg)
   else:
      console.muted ("Cancelled")
      raise typer.Exit (0)

   console.success ("Committed")
   console.hint ("imp commit again, or imp release when ready")
