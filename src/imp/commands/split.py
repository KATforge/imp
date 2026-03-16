import json
import os
import re

import typer

from imp import ai, console, git, prompts, validate


def _build_file_diffs (root: str, files: list [str]) -> str:
   parts = []
   for f in files:
      d = git.diff_file (f)

      full = os.path.join (root, f)
      if not d and os.path.isfile (full):
         try:
            with open (full) as fh:
               lines = fh.readlines () [:30]
            d = "".join ("+" + line for line in lines)
         except Exception:
            pass

      if d:
         snippet = "\n".join (d.splitlines () [:30])
         parts.append (f"--- {f} ---\n{snippet}")
      else:
         parts.append (f"--- {f} --- (no diff available)")

   return "\n".join (parts)


def _validate_response (response: str, all_files: list [str]) -> list [dict] | None:
   try:
      groups = json.loads (response)
   except json.JSONDecodeError:
      console.err ("AI returned invalid JSON")
      return None

   if not isinstance (groups, list) or len (groups) == 0:
      console.err ("AI returned empty or non-array response")
      return None

   grouped = set ()
   for g in groups:
      for f in g.get ("files", []):
         grouped.add (f)

   expected = set (all_files)
   if grouped != expected:
      console.err ("File mismatch: AI groups don't cover all files")
      missing = expected - grouped
      extra = grouped - expected
      if missing:
         console.items ("Missing", "\n".join (sorted (missing)))
      if extra:
         console.items ("Extra", "\n".join (sorted (extra)))
      return None

   for g in groups:
      msg = g.get ("message", "")
      if not validate.commit (msg):
         console.err ("AI output not in Conventional Commits format")
         console.muted (msg)
         return None

   return groups


def split ():
   """Group dirty files into logical commits via AI."""

   git.require ()

   root = git.repo_root ()

   files = git.diff_names ()

   if not files:
      console.err ("No changes to split")
      console.hint ("make some changes first")
      raise typer.Exit (1)

   if len (files) == 1:
      console.err ("Only 1 file changed")
      console.hint ("use imp commit instead")
      raise typer.Exit (1)

   console.header ("Split")

   console.items (f"Files ({len (files)})", "\n".join (files))

   file_diffs = _build_file_diffs (root, files)
   file_diffs = ai.truncate (file_diffs)
   b = git.branch ()

   response = console.spin (
      "Analyzing changes...",
      ai.smart,
      prompts.split (file_diffs, b),
   )
   response = re.sub (r"^```\w*\n?", "", response, flags=re.MULTILINE)
   response = re.sub (r"\n?```$", "", response.strip ())

   groups = _validate_response (response, files)

   if groups is None:
      console.warn ("Retrying...")
      response = console.spin (
         "Re-analyzing...",
         ai.smart,
         prompts.split (file_diffs, b),
      )
      response = re.sub (r"^```\w*\n?", "", response, flags=re.MULTILINE)
      response = re.sub (r"\n?```$", "", response.strip ())
      groups = _validate_response (response, files)

      if groups is None:
         console.err ("Split failed after retry")
         raise typer.Exit (1)

   if len (groups) == 1:
      console.warn ("AI grouped everything into a single commit")
      console.hint ("use imp commit instead")
      raise typer.Exit (0)

   console.out.print ()
   for i, g in enumerate (groups):
      console.label (f"Group {i + 1}: {g ['message']}")
      for f in g ["files"]:
         console.item (f)
      console.out.print ()

   if not console.confirm (f"Commit {len (groups)} groups?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   original_head = git.rev_parse ("HEAD")

   git.stage (all=True)

   try:
      for i, g in enumerate (groups):
         git.reset ("HEAD", soft=False)
         git.add (g ["files"])
         git.commit (g ["message"])
         console.success (f"Group {i + 1}: {g ['message']}")
   except Exception:
      console.warn ("Rolling back...")
      git.reset (original_head, soft=True)
      git.unstage ()
      console.err ("Split failed")
      raise typer.Exit (1)

   console.hint ("imp log to review")
