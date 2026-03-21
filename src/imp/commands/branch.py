import typer

from imp import ai, console, git, prompts, validate


def branch (
   description: list [str] | None = typer.Argument (None, help="Branch description"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Create or switch branches. No args: interactive picker.

   With arguments, uses AI to generate a clean branch name from your
   description. Without arguments, shows local branches with their age
   and lets you pick one to switch to.
   """

   git.require ()

   if not description:
      _switch ()
   else:
      _create (" ".join (description), whisper)


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


def _create (desc: str, whisper: str = ""):
   console.header ("Branch")

   name = ai.fast (prompts.branch_name (desc, whisper))
   name = ai.oneline (name)

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
