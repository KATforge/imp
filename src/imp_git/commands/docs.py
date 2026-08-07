import difflib
import json
import re
from pathlib import Path

import typer
from rich.panel import Panel
from rich.syntax import Syntax

from imp_git import ai, console, git, prompts, repo, validate, version
from imp_git.theme import theme

NO_CHANGE = "NO CHANGE"

def _resolve_root () -> Path:
   docs_path = repo.docs_path ()
   if not docs_path:
      console.hint ('add "docs:path" to .imp, or run imp setup')
      console.fatal ("No docs:path configured")

   root = (Path (git.repo_root ()) / docs_path).resolve ()
   if not root.is_dir ():
      console.fatal (f"docs:path not found: {root}")

   return root

def _candidates (root: Path, include: list [str]) -> list [Path]:
   files = sorted (root.rglob ("*.md"))
   if not include:
      return files

   picked = []
   for f in files:
      rel = f.relative_to (root).as_posix ()
      if any (rel == inc or rel.startswith (inc.rstrip ("/") + "/") for inc in include):
         picked.append (f)

   return picked

def _headings (path: Path) -> str:
   out = []
   for line in path.read_text (errors="ignore").splitlines ():
      stripped = line.strip ()
      if re.match (r"^#{1,3} ", stripped):
         out.append (stripped)
      if len (out) >= 8:
         break
   return " | ".join (out)

def _show_diff (before: str, after: str, path: str):
   diff = "".join (difflib.unified_diff (
      before.splitlines (keepends=True),
      after.splitlines (keepends=True),
      fromfile=f"a/{path}",
      tofile=f"b/{path}",
   ))

   if not diff:
      return

   console.out.print (Panel (
      Syntax (diff, "diff", theme="monokai"),
      border_style=theme.accent,
      title=path,
      title_align="left",
      padding=(1, 2),
   ))
   console.out.print ()

def docs (
   since: str = typer.Option ("", "--since", "-s", help="Tag or commit to analyze from (default: last tag)"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Write all proposed edits without prompting"),
):
   """Sync prose docs against a commit range using AI.

   Reads the .imp docs:path, works out what a range of commits changed, finds
   the doc pages that change could make inaccurate, and proposes edits. Edits
   are written into the docs tree and left uncommitted for review. Reconcile
   mode also corrects statements the code contradicts; additive mode only adds.
   """

   git.require ()

   root = _resolve_root ()
   mode = repo.docs_mode ()
   include = repo.docs_include ()

   console.header ("Docs")

   since_ref = (since or "").strip () or git.last_tag ()
   commits = git.log_full (since=since_ref) if since_ref else git.log_full ()

   if not commits:
      console.muted ("No commits to analyze")
      raise typer.Exit (0)

   console.muted (f"Analyzing {len (commits)} commit(s) since {since_ref or 'the start'}")
   console.out.print ()

   diffs = version.collect_diffs (commits)
   if not diffs:
      console.muted ("No diffs to analyze")
      raise typer.Exit (0)

   summary = console.spin ("Reading the change...", ai.smart, prompts.docs_changes (diffs)).strip ()

   if summary == "NONE" or not summary:
      console.success ("No documentation-relevant changes")
      raise typer.Exit (0)

   console.label ("Change summary")
   console.md (summary)
   console.out.print ()

   cand = _candidates (root, include)
   if not cand:
      console.muted ("No markdown files under docs:path")
      raise typer.Exit (0)

   manifest = "\n".join (f"{p.relative_to (root).as_posix ()} — {_headings (p)}" for p in cand)

   raw = console.spin ("Finding affected pages...", ai.fast, prompts.docs_select (summary, manifest))
   try:
      selected = json.loads (ai.strip_fences (raw).strip ())
   except (json.JSONDecodeError, ValueError):
      selected = []

   by_rel = { p.relative_to (root).as_posix (): p for p in cand }
   targets = [ by_rel [s] for s in selected if s in by_rel ]

   if not targets:
      console.success ("No pages affected")
      raise typer.Exit (0)

   console.label (f"{len (targets)} candidate page(s) [{mode}]")
   console.out.print ()

   edited = 0
   for p in targets:
      rel = p.relative_to (root).as_posix ()
      content = p.read_text (errors="ignore")

      result = ai.strip_fences (
         console.spin (f"Reviewing {rel}...", ai.smart, prompts.docs_edit (summary, rel, content, mode))
      )

      if result.strip () == NO_CHANGE or not result.strip ():
         console.item (f"= {rel} (accurate)")
         continue

      if validate.adds_provenance (content, result):
         console.warn (f"Skipped {rel}: AI attribution or actor ID in proposed text")
         continue

      _show_diff (content, result, rel)

      if yes or console.confirm (f"Write {rel}?"):
         p.write_text (result if result.endswith ("\n") else result + "\n")
         console.success (f"~ {rel}")
         edited += 1
      else:
         console.muted (f"skipped {rel}")

   console.out.print ()
   if edited:
      console.success (f"Updated {edited} page(s), left uncommitted for review")
      console.hint (f"review and commit in {root}")
   else:
      console.muted ("No pages changed")
