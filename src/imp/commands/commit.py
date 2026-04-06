from fnmatch import fnmatch
from typing import Optional

import typer

from imp import ai, console, git, prompts, workflow
from imp.commands import push as push_cmd


def commit (
   all: bool = typer.Option (False, "--all", "-a", help="Stage all changes first"),
   exclude: Optional [list [str]] = typer.Option (None, "--exclude", "-E", help="Glob patterns to exclude from staging"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Accept AI message without review"),
   push: bool = typer.Option (False, "--push", "-p", help="Push to origin after committing"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Generate an AI commit message for staged changes.

   Reads the staged diff and uses AI to produce a Conventional Commits
   message. Use --all/-a to stage everything first. You can review, edit,
   or cancel the message before committing.
   """

   git.require ()

   if all:
      git.stage ()

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
      console.hint ("git add <files>, or imp commit -a")
      console.fatal ("Nothing staged")

   d = ai.truncate (d)

   console.header ("Commit")

   b = git.branch ()
   msg = ai.commit_message (prompts.commit (d, b, whisper))

   workflow.review_commit (msg, yes)

   console.success ("Committed")

   if push:
      console.out.print ()
      push_cmd.do_push ()
      return

   console.hint ("imp commit again, or imp release when ready")
