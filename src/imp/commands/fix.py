import json
import shutil
import subprocess

import typer

from imp import ai, console, git, prompts, validate


def fix (
   issue: int = typer.Argument (..., help="GitHub issue number"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Create a branch from a GitHub issue.

   Fetches the issue title and body from GitHub using the gh CLI, then
   uses AI to generate a branch name. After creation, displays the issue
   context so you can start working immediately.
   """

   git.require ()

   if not shutil.which ("gh"):
      console.err ("GitHub CLI (gh) not installed")
      console.hint ("https://cli.github.com")
      raise typer.Exit (1)

   console.header (f"Fix Issue #{issue}")

   try:
      result = console.spin (
         "Fetching issue...",
         subprocess.run,
         [ "gh", "issue", "view", str (issue), "--json", "title,body,labels" ],
         capture_output=True,
         text=True,
         check=True,
      )
      data = json.loads (result.stdout)
   except Exception as e:
      console.err (f"Could not fetch issue #{issue}: {e}")
      raise typer.Exit (1) from None

   title = data.get ("title", "")
   body = (data.get ("body", "") or "") [:500]

   console.label ("Issue")
   console.item (f"#{issue}: {title}")
   console.out.print ()

   name = ai.fast (prompts.fix (title, body, whisper))
   name = ai.oneline (name)

   if not validate.branch (name):
      console.err (f"Invalid branch name: {name}")
      raise typer.Exit (1)

   console.label ("Branch")
   console.item (name)
   console.out.print ()

   if console.confirm ("Create branch?"):
      git.checkout (name, create=True)
      console.success (f"Switched to {name}")
      console.out.print ()
      console.label ("Context")
      console.divider ()
      console.out.print (title)
      console.out.print ()
      body_preview = "\n".join (body.splitlines () [:10])
      if body_preview:
         console.out.print (body_preview)
      console.divider ()
      console.hint ("make changes, then imp commit")
   else:
      console.muted ("Cancelled")
      raise typer.Exit (0)
