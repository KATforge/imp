from typing import Optional

import typer

from imp import ai, console, git, prompts, validate


def branch (
   description: Optional [list [str]] = typer.Argument (None, help="Branch description"),
):
   """Create or switch branches. No args: interactive picker."""

   git.require ()

   if not description:
      _switch ()
   else:
      _create (" ".join (description))


def _switch ():
   console.header ("Branches")

   branches = git.branches_local ()
   if len (branches) <= 1:
      console.muted ("Only one branch exists")
      raise typer.Exit (0)

   labels = []
   for b in branches:
      age = git.branch_age (b)
      labels.append (f"{b}  ({age})")

   choice = console.choose ("Switch to:", labels)
   target = choice.split ("  (") [0]

   current = git.branch ()
   if target == current:
      console.muted (f"Already on {target}")
      raise typer.Exit (0)

   git.require_clean ()
   git.checkout (target)
   console.success (f"Switched to {target}")


def _create (desc: str):
   console.header ("Branch")

   name = ai.fast (prompts.branch_name (desc))
   name = ai.sanitize (name)

   if not validate.branch (name):
      console.err (f"Invalid branch name: {name}")
      raise typer.Exit (1)

   console.label ("Suggested")
   console.item (name)
   console.out.print ()

   if console.confirm ("Create branch?"):
      git.checkout (name, create=True)
      console.success (f"Switched to {name}")
      console.hint ("make changes, then imp commit")
   else:
      console.muted ("Cancelled")
      raise typer.Exit (0)
