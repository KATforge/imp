import difflib
from pathlib import Path

import typer
from rich.panel import Panel
from rich.syntax import Syntax

from imp import ai, console, git, prompts
from imp.theme import theme

MARKER = "<<<<<<<"
SEPARATOR = "---RESOLVED---"

def _theirs_branch () -> str:
   gd = git.git_dir ()

   merge_msg = Path (gd, "MERGE_MSG")
   if merge_msg.exists ():
      first_line = merge_msg.read_text ().splitlines () [0]
      parts = first_line.split ("'")
      if len (parts) >= 2:
         return parts [1]

   return "incoming"

def _parse_response (raw: str) -> tuple [str, str]:
   if SEPARATOR in raw:
      parts = raw.split (SEPARATOR, 1)
      return parts [0].strip (), parts [1].strip ()

   return "", raw.strip ()

def _make_diff (original: str, resolved: str, path: str) -> str:
   orig_lines = original.splitlines (keepends=True)
   res_lines = resolved.splitlines (keepends=True)

   diff = difflib.unified_diff (
      orig_lines,
      res_lines,
      fromfile=f"a/{path} (conflicted)",
      tofile=f"b/{path} (resolved)",
   )

   return "".join (diff)

def _show_suggestion (content: str, result: str, reasoning: str, path: str):
   if reasoning:
      console.out.print (Panel (
         reasoning,
         border_style=theme.muted,
         title="Reasoning",
         title_align="left",
         padding=(1, 2),
      ))

   diff_text = _make_diff (content, result, path)

   if diff_text:
      console.out.print (Panel (
         Syntax (diff_text, "diff", theme="monokai"),
         border_style=theme.accent,
         title=path,
         title_align="left",
         padding=(1, 2),
      ))
   else:
      console.out.print (Panel (
         result,
         border_style=theme.accent,
         title=path,
         title_align="left",
         padding=(1, 2),
      ))

   console.out.print ()

def resolve (
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
   favor_ours: bool = typer.Option (False, "--ours", help="Bias AI toward our branch"),
   favor_theirs: bool = typer.Option (False, "--theirs", help="Bias AI toward their branch"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Auto-accept all AI suggestions"),
):
   """Resolve merge conflicts with AI assistance.

   Walks through each conflicted file, sends it to AI for resolution,
   and lets you accept, edit, or choose ours/theirs for each file.
   """

   if favor_ours and favor_theirs:
      console.fatal ("Cannot use --ours and --theirs together")

   favor = "ours" if favor_ours else "theirs" if favor_theirs else ""

   git.require ()

   files = git.conflicts ()
   if not files:
      console.muted ("No conflicts to resolve")
      raise typer.Exit (0)

   console.header ("Resolve")

   console.label (f"{len (files)} conflicted file(s)")
   for f in files:
      console.item (f)
   console.out.print ()

   root = Path (git.repo_root ())
   ours = git.branch () or "HEAD"
   theirs = _theirs_branch ()

   if favor:
      side = ours if favor == "ours" else theirs
      console.muted (f"Favoring {favor} ({side})")
      console.out.print ()

   num_resolved = 0
   num_skipped = 0

   for i, path in enumerate (files):
      if i > 0:
         console.out.print ()
      console.label (path)
      console.out.print ()

      try:
         content = Path (path).read_text ()
      except (OSError, UnicodeDecodeError) as e:
         console.muted (f"Skipped (unreadable: {e})")
         num_skipped += 1
         continue

      has_markers = MARKER in content

      if not has_markers:
         console.muted ("No conflict markers (delete/rename conflict)")

         if yes:
            git.add ([ path ])
            num_resolved += 1
            continue

         choice = console.choose (
            "Resolution",
            [ "Keep", "Delete", "Skip" ],
         )

         if choice == "Keep":
            git.add ([ path ])
            num_resolved += 1
         elif choice == "Delete":
            git.rm (path)
            num_resolved += 1
         else:
            num_skipped += 1

         continue

      raw = ai.smart (prompts.resolve (content, path, ours, theirs, whisper, favor))
      reasoning, result = _parse_response (raw)

      if MARKER in result:
         console.warn ("AI left conflict markers, retrying...")
         console.out.print ()

         raw = ai.smart (prompts.resolve (content, path, ours, theirs, whisper, favor))
         reasoning, result = _parse_response (raw)

         if MARKER in result:
            console.warn ("AI still left markers, showing best attempt")

      if yes:
         _show_suggestion (content, result, reasoning, path)
         choice = "Accept"
      else:
         while True:
            _show_suggestion (content, result, reasoning, path)

            choice = console.choose (
               "Resolution",
               [ "Accept", "Discuss", "Ours", "Theirs", "Edit", "Skip" ],
            )

            if choice == "Discuss":
               feedback = console.prompt ("Feedback")

               if not feedback.strip ():
                  continue

               console.out.print ()

               raw = ai.smart (prompts.resolve_revise (
                  content, path, ours, theirs,
                  result, reasoning, feedback, favor,
               ))
               reasoning, result = _parse_response (raw)

               if MARKER in result:
                  console.warn ("AI left conflict markers in revision")

               continue

            break

      if choice == "Accept":
         (root / path).write_text (result)
         git.add ([ path ])
         num_resolved += 1
      elif choice == "Ours":
         git.checkout_side (path, "ours")
         git.add ([ path ])
         num_resolved += 1
      elif choice == "Theirs":
         git.checkout_side (path, "theirs")
         git.add ([ path ])
         num_resolved += 1
      elif choice == "Edit":
         edited = console.edit (result)
         if edited.strip ():
            (root / path).write_text (edited)
            git.add ([ path ])
            num_resolved += 1
         else:
            console.muted ("Empty content, skipped")
            num_skipped += 1
      else:
         num_skipped += 1

   console.out.print ()
   console.success (f"{num_resolved} resolved, {num_skipped} skipped")

   if num_skipped == 0 and num_resolved > 0:
      if git.merge_in_progress ():
         console.hint ("git merge --continue")
      elif git.rebase_in_progress ():
         console.hint ("git rebase --continue")
      else:
         console.hint ("All conflicts resolved")
