import json
import subprocess

import typer

from imp import ai, console, git, prompts

MIN_SCORE = 40

def fixup (
   target: str = typer.Argument ("", help="Explicit commit (sha or pattern); default: AI picks"),
   auto: bool = typer.Option (False, "--auto", "-a", help="Accept top match without prompting"),
   squash: bool = typer.Option (False, "--squash", "-s", help="Also run rebase --autosquash if safe"),
   since: str = typer.Option ("", "--since", help="Widen lookback (e.g. '1 week ago')"),
   count: int = typer.Option (20, "--count", "-n", help="How many recent commits to consider"),
):
   """Create a fixup commit against the right historical commit.

   Reads staged changes, asks AI to match against recent commits, and
   commits with --fixup=<sha>. With --squash, follows up with a
   non-interactive autosquash rebase (refused if the target is pushed).
   """

   git.require ()

   if not git.staged_files ():
      console.hint ("git add <files> first")
      console.fatal ("Nothing staged")

   staged = ai.truncate (git.diff (staged=True))

   console.header ("Fixup")

   if target:
      sha = git.rev_parse (target)
      if not sha:
         console.fatal (f"Cannot resolve target: {target}")
      console.label ("Target")
      console.item (f"{sha [:12]}  {git.show_oneline (sha).split (' ', 1) [1] if ' ' in git.show_oneline (sha) else ''}")
      _do_fixup (sha, squash, auto)
      return

   candidates = git.recent_commit_diffs (count=count, since=since)
   if not candidates:
      console.hint ("imp commit instead")
      console.fatal ("No commits found in lookback")

   pick = _ai_pick (staged, candidates)
   sha_full = _resolve_candidate (pick ["best"], candidates)

   if not sha_full:
      console.fatal (f"AI picked unknown sha: {pick ['best']}")

   if pick ["score"] < MIN_SCORE:
      console.warn (f"AI confidence low ({pick ['score']}/100): {pick ['reason']}")
      if not console.confirm ("Proceed anyway?"):
         console.muted ("Cancelled")
         raise typer.Exit (0)

   subject = next ((c ["subject"] for c in candidates if c ["hash"] == sha_full), "")

   console.label ("Best match")
   console.item (f"{sha_full [:12]}  {subject}")
   console.item (f"score: {pick ['score']}/100")
   console.item (f"why:   {pick ['reason']}")

   if pick.get ("alternates"):
      console.out.print ()
      console.label ("Alternates")
      for alt in pick ["alternates"] [:3]:
         alt_sha = _resolve_candidate (alt.get ("sha", ""), candidates)
         if not alt_sha:
            continue
         alt_subject = next ((c ["subject"] for c in candidates if c ["hash"] == alt_sha), "")
         console.item (f"{alt_sha [:7]}  ({alt.get ('score', 0)})  {alt_subject}")

   console.out.print ()

   if not auto and not console.confirm ("Create fixup for this commit?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   _do_fixup (sha_full, squash, auto)

def _do_fixup (sha: str, squash: bool, auto: bool):
   try:
      git.commit_fixup (sha)
   except subprocess.CalledProcessError as e:
      detail = (e.stderr or e.stdout or "").strip ()
      console.fatal (f"git commit --fixup failed: {detail}" if detail else "git commit --fixup failed")

   console.success (f"Fixup committed against {sha [:7]}")

   if not squash:
      console.hint (f"imp fixup --squash, or git rebase -i --autosquash {sha}^")
      return

   if git.has_upstream ():
      upstream = git.rev_parse ("@{u}")
      if upstream and git.count_between (sha, upstream) > 0:
         console.warn (f"Target {sha [:7]} is already pushed; refusing to autosquash")
         console.hint ("rewriting pushed history is destructive; finish manually if intended")
         raise typer.Exit (1)

   if not auto and not console.confirm (f"Run rebase --autosquash against {sha [:7]}^?"):
      console.muted ("Skipped autosquash")
      return

   try:
      git.autosquash_rebase (f"{sha}^")
   except subprocess.CalledProcessError as e:
      detail = (e.stderr or e.stdout or "").strip ()
      console.fatal (f"autosquash rebase failed: {detail}" if detail else "autosquash rebase failed")

   console.success ("Autosquash complete")

def _ai_pick (staged: str, candidates: list [dict [str, str]]) -> dict:
   blocks = []
   for c in candidates:
      blocks.append (f"{c ['hash'] [:12]} {c ['subject']}\n{ai.truncate (c ['diff'], max_lines=80)}")

   prompt = prompts.fixup_pick (staged, "\n\n".join (blocks))
   raw = ai.strip_fences (ai.smart (prompt))

   try:
      data = json.loads (raw)
   except json.JSONDecodeError:
      console.muted (raw)
      console.fatal ("AI did not return valid JSON")

   if not isinstance (data, dict) or "best" not in data:
      console.muted (raw)
      console.fatal ("AI response missing 'best' field")

   data.setdefault ("score", 0)
   data.setdefault ("reason", "")
   data.setdefault ("alternates", [])

   return data

def _resolve_candidate (prefix: str, candidates: list [dict [str, str]]) -> str:
   if not prefix:
      return ""
   for c in candidates:
      if c ["hash"].startswith (prefix):
         return c ["hash"]
   return ""
