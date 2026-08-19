import re
from typing import Annotated, Any

import typer
from rich import box
from rich.table import Table
from rich.text import Text

from imp_git import ai, console, features, git, result, runtime, state
from imp_git.theme import theme

_HUNK = re.compile (r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _scope (feature: str) -> tuple [str, str, str]:
   """Resolve what to review: base, tip, and a readable label."""

   trunk = git.base_branch ()
   if feature:
      value = features.resolve (feature)
      base = git.merge_base (trunk, str (value ["branch"]))
      return base, str (value ["branch"]), f"{value ['branch']} against {trunk}"
   if not git.remote_exists ():
      raise state.StateError ("No origin to compare against; name a feature to review instead")
   git.fetch (remote="origin", refspec=f"+refs/heads/{trunk}:refs/remotes/origin/{trunk}")
   remote = f"origin/{trunk}"
   if not git.rev_parse (remote):
      raise state.StateError (f"Cannot resolve {remote}")
   return remote, trunk, f"unpushed {trunk}"


def _hunks (diff: str) -> list [dict [str, Any]]:
   """Split one unified diff into per-file hunks with new-file line ranges."""

   values: list [dict [str, Any]] = []
   current_file = ""
   hunk: dict [str, Any] | None = None
   for line in diff.splitlines ():
      if line.startswith ("diff --git"):
         current_file = ""
         hunk = None
         continue
      if line.startswith ("+++ "):
         current_file = line [4:].removeprefix ("b/").strip ()
         continue
      match = _HUNK.match (line)
      if match:
         start = int (match.group (1))
         length = int (match.group (2) or "1")
         hunk = { "file": current_file, "start": start, "end": start + length, "lines": [ line ] }
         values.append (hunk)
         continue
      if hunk is not None:
         hunk ["lines"].append (line)
   return values


def _styled (lines: list [str]) -> Text:
   text = Text ()
   for line in lines:
      if line.startswith ("+"):
         style = theme.success
      elif line.startswith ("-"):
         style = theme.error
      elif line.startswith ("@@"):
         style = theme.accent
      else:
         style = theme.muted
      text.append (line + "\n", style=style)
   text.rstrip ()
   return text


def _match (annotations: list [dict [str, Any]], hunk: dict [str, Any], first_of_file: bool) -> list [str]:
   notes = []
   for value in annotations:
      if str (value.get ("file", "")) != hunk ["file"]:
         continue
      line = value.get ("line")
      inside = isinstance (line, int) and hunk ["start"] <= line < hunk ["end"]
      if inside or (line is None and first_of_file):
         severity = str (value.get ("severity", "info"))
         notes.append (f"[{severity}] {value.get ('note', '')}")
         value ["placed"] = True
   return notes


def _render (label: str, review: dict [str, Any], diff: str):
   console.header (f"Review: {label}")
   console.md (str (review.get ("summary", "")))
   console.out.print ()
   annotations = [ dict (value) for value in review.get ("annotations", []) ]
   table = Table (box=box.ROUNDED, header_style="accent", border_style=theme.muted, show_lines=True)
   table.add_column ("Diff", overflow="fold", ratio=3)
   table.add_column ("Notes", overflow="fold", ratio=1)
   seen_files: set [str] = set ()
   for hunk in _hunks (diff):
      first = hunk ["file"] not in seen_files
      seen_files.add (hunk ["file"])
      notes = _match (annotations, hunk, first)
      left = Text ()
      if first:
         left.append (hunk ["file"] + "\n", style=f"bold {theme.accent}")
      left.append (_styled (hunk ["lines"]))
      table.add_row (left, "\n".join (notes))
   console.out.print (table)
   strays = [ value for value in annotations if not value.get ("placed") ]
   for value in strays:
      console.warn (f"{value.get ('file', '?')}: {value.get ('note', '')}")


def _questions (diff: str):
   while console.interactive ():
      question = console.ask ("Ask about this diff (empty to finish)")
      if not question:
         return
      console.md (ai.answer (diff, question))
      console.out.print ()


def review (
   feature: Annotated [
      str,
      typer.Argument (help="Feature to review before integration; omit to review unpushed trunk"),
   ] = "",
   ask: Annotated [
      str,
      typer.Option ("--ask", help="One question about the diff; prints the answer and exits"),
   ] = "",
):
   """Read an AI-annotated diff: the change on the left, findings on the right.

   With no argument it reviews everything on trunk that origin does not have yet, which
   is exactly the layer integrated by `imp done` and not pushed. Name a feature to
   review its branch against trunk before integrating.

   The diff is shown per hunk with AI annotations aligned beside the code they concern,
   ranked info, warn, or risk, under a short summary. Afterwards, keep asking free-form
   questions about the diff at the prompt. Use --ask for a single scripted question.

   Advisory only: writes nothing and changes nothing. Sends the diff, and any question
   you type, to the configured AI provider.
   """

   git.require ()
   try:
      base, tip, label = _scope (feature)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   diff = git.capture ("diff", base, tip)
   if not diff:
      console.success (f"Nothing to review: {label} is empty")
      return { "annotations": [], "scope": label, "summary": "" }
   if ask:
      try:
         reply = ai.answer (diff, ask)
      except state.StateError as error:
         console.fatal (str (error))
      if runtime.options.json:
         return result.emit (
            "imp.review-answer.v1", "imp review",
            { "answer": reply, "question": ask, "scope": label }, json_output=True,
         )
      console.md (reply)
      return { "answer": reply, "question": ask, "scope": label }
   try:
      value = ai.review_diff (diff)
   except state.StateError as error:
      console.fatal (str (error))
   data = {
      "annotations": value.get ("annotations", []),
      "commits": git.log_oneline (rev_range=f"{base}..{tip}").splitlines (),
      "scope": label,
      "summary": str (value.get ("summary", "")),
   }
   if runtime.options.json:
      return result.emit ("imp.review.v1", "imp review", data, json_output=True)
   _render (label, value, diff)
   _questions (diff)
   return data
