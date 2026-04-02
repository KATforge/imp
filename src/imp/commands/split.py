import json
from datetime import datetime, timezone
from pathlib import Path

import typer

from imp import ai, console, git, prompts, validate


def _build_file_stats (files: list [str]) -> str:
   numstat = git.diff_numstat ()

   stat_map = {}
   for line in numstat.splitlines ():
      parts = line.split ("\t", 2)
      if len (parts) == 3:
         stat_map [parts [2]] = f"{parts [0]}+\t{parts [1]}-"

   lines = []
   for f in files:
      stat = stat_map.get (f, "new")
      lines.append (f"{stat}\t{f}")

   return "\n".join (lines)


def _build_file_diffs (root: str, files: list [str]) -> str:
   parts = []
   for f in files:
      d = git.diff_file (f)

      full = Path (root) / f
      if not d and full.is_file ():
         try:
            lines = full.read_text ().splitlines (keepends=True) [:30]
            d = "".join ("+" + line for line in lines)
         except (OSError, UnicodeDecodeError):
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


def do_split (files: list [str], whisper: str = "", yes: bool = False):
   """Core split logic. Stages, groups, and commits files.

   Returns the list of committed groups. Raises typer.Exit on failure.
   """

   root = git.repo_root ()

   console.items (f"Files ({len (files)})", "\n".join (files))

   file_diffs = _build_file_diffs (root, files)
   b = git.branch ()

   is_large = len (file_diffs.splitlines ()) > ai.MAX_DIFF_LINES

   if is_large:
      stats = _build_file_stats (files)
      prompt = prompts.split_plan (stats, b, whisper)
   else:
      prompt = prompts.split (file_diffs, b, whisper)

   response = ai.strip_fences (ai.smart (prompt))
   groups = _validate_response (response, files)

   if groups is None:
      console.warn ("Retrying...")
      response = ai.strip_fences (ai.smart (prompt))
      groups = _validate_response (response, files)

      if groups is None:
         console.fatal ("Split failed after retry")

   if len (groups) == 1:
      return None

   console.out.print ()
   for i, g in enumerate (groups):
      console.label (f"Group {i + 1}: {g ['message']}")
      for f in g ["files"]:
         console.item (f)
      console.out.print ()

   if not yes and not console.confirm (f"Commit {len (groups)} groups?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   for g in groups:
      mtimes = []
      for f in g ["files"]:
         full = Path (root) / f
         if full.exists ():
            mtimes.append (full.stat ().st_mtime)
      g ["date"] = max (mtimes) if mtimes else 0

   groups.sort (key=lambda g: g ["date"])

   original_head = git.rev_parse ("HEAD")
   is_fresh = git.commit_count () == 0

   git.stage (all=True)

   try:
      for i, g in enumerate (groups):
         git.unstage ()
         git.add (g ["files"])

         date = ""
         if g ["date"] > 0:
            dt = datetime.fromtimestamp (g ["date"], tz=timezone.utc)
            date = dt.strftime ("%Y-%m-%dT%H:%M:%S%z")

         git.commit (g ["message"], date=date)
         console.success (f"Group {i + 1}: {g ['message']}")
   except Exception as e:
      console.err (f"Split failed: {e}")
      console.warn ("Rolling back...")
      if is_fresh:
         git.unstage ()
      else:
         git.reset (original_head, soft=True)
         git.unstage ()
      raise typer.Exit (1) from None

   return groups


def split (
   yes: bool = typer.Option (False, "--yes", "-y", help="Accept AI grouping without review"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Group dirty files into logical commits via AI.

   Analyzes all changed files and uses AI to partition them into logical
   groups, each with its own Conventional Commits message. Commits each
   group sequentially. Rolls back if any commit fails. Requires at least
   two changed files.
   """

   git.require ()

   files = git.diff_names ()

   if not files:
      console.hint ("make some changes first")
      console.fatal ("No changes to split")

   if len (files) == 1:
      console.hint ("use imp commit instead")
      console.fatal ("Only 1 file changed")

   console.header ("Split")

   result = do_split (files, whisper, yes)

   if result is None:
      console.warn ("AI grouped everything into a single commit")
      console.hint ("use imp commit instead")
      raise typer.Exit (0)

   console.hint ("imp log to review")
