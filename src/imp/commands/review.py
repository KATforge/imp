import shutil
import subprocess
import tempfile

import typer

from imp import ai, console, git, prompts

def _handoff (findings: str, dangerous: bool = False):
   if not shutil.which ("claude"):
      console.hint ("curl -fsSL https://claude.ai/install.sh | bash")
      console.fatal ("claude CLI not found")

   prompt = f"Fix the following code review findings. Apply each fix directly to the files.\n\n{findings}"

   with tempfile.NamedTemporaryFile (mode="w", suffix=".md", delete=True) as f:
      f.write (prompt)
      f.flush ()

      cmd = [ "claude" ]
      if dangerous:
         cmd.append ("--dangerously-skip-permissions")
      cmd.append (f"Read {f.name} and follow the instructions inside.")

      console.out.print ()
      console.muted ("Handing off to claude CLI...")
      console.out.print ()
      subprocess.run (cmd, check=False)

def review (
   last: int = typer.Option (0, "--last", "-l", help="Review the last N commits"),
   fix: bool = typer.Option (False, "--fix", "-f", help="Send review findings to the claude CLI for fixing"),
   dangerous: bool = typer.Option (False, "--dangerous", "-d", help="Skip claude CLI permission prompts"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """AI code review of current changes.

   Sends staged changes (or unstaged if nothing is staged) to the smart
   AI model for review. Outputs feedback in markdown covering bugs, style
   issues, and suggestions. Use --last to review recent commits instead.
   Use --fix to hand findings off to the claude CLI.
   """

   git.require ()

   console.header ("Review")

   if last > 0:
      d = git.diff_range (f"HEAD~{last}..HEAD")
   else:
      d = git.diff (staged=True)

      if not d:
         d = git.diff ()

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
   console.out.print ()

   should_fix = fix
   if not fix:
      choice = console.choose ("Next?", [ "Fix with claude CLI", "Done" ])
      should_fix = choice == "Fix with claude CLI"

   if should_fix:
      _handoff (result, dangerous)
