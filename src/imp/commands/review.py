import shutil
import subprocess
import tempfile

import typer

from imp import ai, console, git, prompts


def _handoff (findings: str):
   if not shutil.which ("claude"):
      console.err ("Claude Code not found")
      console.hint ("curl -fsSL https://claude.ai/install.sh | bash")
      raise typer.Exit (1)

   prompt = f"Fix the following code review findings. Apply each fix directly to the files.\n\n{findings}"

   with tempfile.NamedTemporaryFile (mode="w", suffix=".md", delete=True) as f:
      f.write (prompt)
      f.flush ()

      console.out.print ()
      console.muted ("Handing off to Claude Code...")
      subprocess.run (
         [ "claude", f"Read {f.name} and follow the instructions inside." ],
         check=False,
      )


def review (
   fix: bool = typer.Option (False, "--fix", "-f", help="Send review findings to Claude Code for fixing"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """AI code review of current changes.

   Sends staged changes (or unstaged if nothing is staged) to the smart
   AI model for review. Outputs feedback in markdown covering bugs, style
   issues, and suggestions. Use --fix to send findings to Claude Code.
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
      "Thinking...",
      ai.smart,
      prompts.review (d, whisper),
      False,
   )

   console.divider ()
   console.md (result)
   console.divider ()

   should_fix = fix
   if not fix:
      choice = console.choose ("Next?", [ "Fix with Claude Code", "Done" ])
      should_fix = choice == "Fix with Claude Code"

   if should_fix:
      _handoff (result)
