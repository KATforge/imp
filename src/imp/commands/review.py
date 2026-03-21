import typer

from imp import ai, console, git, prompts


def review (
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """AI code review of current changes.

   Sends staged changes (or unstaged if nothing is staged) to the smart
   AI model for review. Outputs feedback in markdown covering bugs, style
   issues, and suggestions.
   """

   git.require ()

   console.header ("Review")

   d = git.diff (staged=True)
   context = "staged changes"

   if not d:
      d = git.diff ()
      context = "unstaged changes"

   if not d:
      console.muted ("No changes to review")
      console.hint ("make some changes first")
      raise typer.Exit (0)

   d = ai.truncate (d)

   result = console.spin (
      f"Reviewing {context}...",
      ai.smart,
      prompts.review (d, whisper),
   )

   console.divider ()
   console.md (result)
   console.divider ()

   console.hint ("imp commit to commit, or keep editing")
