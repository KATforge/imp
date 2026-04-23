import typer

from imp import ai, console, gh, git, prompts, validate

def fix (
   issue: int = typer.Argument (..., help="GitHub issue number"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Accept suggested branch name"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Create a branch from a GitHub issue.

   Fetches the issue title and body from GitHub using the gh CLI, then
   uses AI to generate a branch name. After creation, displays the issue
   context so you can start working immediately.
   """

   git.require ()
   gh.require ()

   console.header (f"Fix Issue #{issue}")

   data = console.spin ("Fetching issue...", gh.issue, issue)

   title = data.get ("title", "")
   body = (data.get ("body", "") or "") [:500]

   console.label ("Issue")
   console.item (f"#{issue}: {title}")
   console.out.print ()

   name = ai.fast (prompts.fix (title, body, whisper))
   name = ai.oneline (name)

   if not validate.branch (name):
      console.fatal (f"Invalid branch name: {name}")

   console.label ("Branch")
   console.item (name)
   console.out.print ()

   if yes or console.confirm ("Create branch?"):
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
