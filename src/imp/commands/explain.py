from pathlib import Path

import typer

from imp import ai, console, git, prompts

def explain (
   target: str = typer.Argument ("", help="Commit, range (a..b), or file path; default: HEAD"),
   staged: bool = typer.Option (False, "--staged", "-s", help="Explain staged changes"),
   brief: bool = typer.Option (False, "--brief", "-b", help="Short explanation"),
   full: bool = typer.Option (False, "--full", "-f", help="Longer, more detailed explanation"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Explain a diff, commit, range, or file in plain English.

   Resolves the target to a diff and uses AI to narrate what changed and
   why. Default target is HEAD. Use --staged for the current staging area
   or pass a file path to summarize its recent history.
   """

   git.require ()

   if brief and full:
      console.fatal ("--brief and --full are mutually exclusive")

   mode = "balanced"
   if brief:
      mode = "brief"
   elif full:
      mode = "full"

   console.header ("Explain")

   diff_text, label = _resolve (target, staged)

   if not diff_text:
      console.muted ("Nothing to explain")
      raise typer.Exit (0)

   console.label ("Target")
   console.item (label)
   console.out.print ()

   diff_text = ai.truncate (diff_text)

   result = console.spin (
      "Thinking...",
      ai.smart,
      prompts.explain (diff_text, mode, whisper),
   )

   console.divider ()
   console.md (result)
   console.divider ()

def explain_diff (diff: str, mode: str = "balanced", whisper: str = "") -> str:
   """Reusable primitive: AI explanation of an arbitrary diff."""

   diff = ai.truncate (diff)
   return ai.smart (prompts.explain (diff, mode, whisper))

def _resolve (target: str, staged: bool) -> tuple [str, str]:
   if staged:
      return git.diff (staged=True), "staged changes"

   if not target:
      return git.show_patch ("HEAD"), "HEAD"

   if ".." in target:
      return git.diff_range (target), target

   if Path (target).exists ():
      entries = git.log_full ()
      file_entries = [ e for e in entries if _touches (e ["hash"], target) ]
      if not file_entries:
         d = git.diff_file (target)
         return d, f"{target} (working tree)"

      recent = file_entries [-5:]
      blocks = []
      for e in recent:
         patch = git.show_patch (e ["hash"])
         blocks.append (f"--- commit {e ['hash'] [:7]}: {e ['subject']}\n{patch}")
      return "\n\n".join (blocks), f"{target} (last {len (recent)} commits touching it)"

   hash_ = git.rev_parse (target)
   if hash_:
      return git.show_patch (target), target

   console.fatal (f"Cannot resolve target: {target}")

def _touches (ref: str, path: str) -> bool:
   from imp.git import _run
   result = _run ("show", "--name-only", "--format=", ref, check=False)
   files = [ f.strip () for f in result.stdout.splitlines () if f.strip () ]
   return path in files
