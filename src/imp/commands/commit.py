import typer

from imp import ai, console, git, prompts


def commit (
   all: bool = typer.Option (False, "--all", "-a", help="Stage all changes first"),
):
   """Generate an AI commit message for staged changes."""

   git.require ()

   if all:
      git.stage (all=True)

   d = git.diff (staged=True)
   if not d:
      console.err ("Nothing staged")
      console.hint ("git add <files>, or imp commit -a")
      raise typer.Exit (1)

   console.header ("Commit")

   b = git.branch ()
   msg = ai.commit_message (prompts.commit (d, b))

   choice = console.review (msg)

   if choice == "Edit":
      git.commit (msg, edit=True)
   elif choice == "Yes":
      git.commit (msg)
   else:
      console.muted ("Cancelled")
      raise typer.Exit (0)

   console.success ("Committed")
   console.hint ("imp commit again, or imp release when ready")
