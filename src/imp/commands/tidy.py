import json
import subprocess
import time

import typer

from imp import ai, console, git, prompts, validate

MAX_PLAN_RETRIES = 1

def tidy (
   range: str = typer.Argument ("", help="Range: count (5), ref (main), 'a..b', or '1 year ago'"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Accept AI plan without review"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Rewrite past commit history into a clean sequence.

   Groups, rewords, squashes, and drops commits using AI. The original
   state is saved to a backup ref so you can recover on failure.
   """
   git.require ()
   console.header ("Tidy")

   git.require_clean (hint="commit or stash first")

   if git.rebase_in_progress () or git.merge_in_progress ():
      console.fatal ("Finish the in-progress rebase or merge first")

   base = _resolve_base (range)
   commits = git.log_full (since=base)

   if not commits:
      console.muted ("No commits in range")
      raise typer.Exit (0)

   if len (commits) < 2:
      console.hint ("imp amend rewords a single commit")
      console.fatal ("Need at least 2 commits to tidy")

   pushed = _pushed_count (base)
   if pushed > 0:
      console.warn (f"{pushed} commit(s) in range are already pushed")
      if not console.confirm ("Rewriting pushed history is destructive. Continue?"):
         console.muted ("Cancelled")
         raise typer.Exit (0)

   console.items (
      f"Current history ({len (commits)} commits)",
      "\n".join (f"{c ['hash'] [:7]}  {c ['subject']}" for c in commits),
   )
   console.out.print ()

   plan = _get_plan (commits, whisper)
   _show_plan (plan, commits)

   if not yes and not console.confirm ("Apply this plan?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   _apply (plan, base)

   console.success (f"Tidied {len (commits)} commits")
   console.hint ("imp log to inspect, or reflog to recover")

def _resolve_base (expr: str) -> str:
   if not expr:
      if git.has_upstream ():
         hash_ = git.rev_parse ("@{u}")
         if hash_:
            return hash_
      console.hint ("e.g. imp tidy 5  or  imp tidy '1 year ago'")
      console.fatal ("No upstream set, specify a range")

   if expr.isdigit ():
      hash_ = git.rev_parse (f"HEAD~{expr}")
      if not hash_:
         console.fatal (f"Cannot resolve HEAD~{expr}")
      return hash_

   if ".." in expr:
      left = expr.split ("..", 1) [0]
      hash_ = git.rev_parse (left)
      if not hash_:
         console.fatal (f"Cannot resolve ref: {left}")
      return hash_

   hash_ = git.rev_parse (expr)
   if hash_ and hash_ != expr:
      return hash_

   entries = git.log_since (expr)
   if entries:
      oldest_parent = git.rev_parse (f"{entries [0] ['hash']}^")
      if oldest_parent:
         return oldest_parent
      console.fatal ("Range reaches the root commit, not supported")

   iso = ai.oneline (ai.fast (prompts.tidy_date (expr)))
   if iso and _looks_like_date (iso):
      entries = git.log_since (iso)
      if entries:
         oldest_parent = git.rev_parse (f"{entries [0] ['hash']}^")
         if oldest_parent:
            return oldest_parent

   console.fatal (f"Cannot resolve range: {expr}")

def _looks_like_date (text: str) -> bool:
   return len (text) >= 8 and text [:4].isdigit () and "-" in text

def _pushed_count (base: str) -> int:
   if not git.has_upstream ():
      return 0

   upstream = git.rev_parse ("@{u}")
   if not upstream:
      return 0

   return git.count_between (base, upstream)

def _get_plan (commits: list [dict [str, str]], whisper: str) -> list [dict]:
   lines = "\n".join (f"{c ['hash'] [:12]} {c ['subject']}" for c in commits)
   prompt = prompts.tidy (lines, branch=git.branch (), whisper=whisper)

   last_raw = ""
   for attempt in range (MAX_PLAN_RETRIES + 1):
      raw = ai.strip_fences (ai.smart (prompt))
      last_raw = raw

      try:
         plan = json.loads (raw)
      except json.JSONDecodeError:
         if attempt < MAX_PLAN_RETRIES:
            console.warn ("Retrying (invalid JSON)...")
            console.out.print ()
            continue
         console.muted (raw)
         console.fatal ("AI did not return valid JSON")

      if not isinstance (plan, list) or not plan:
         if attempt < MAX_PLAN_RETRIES:
            console.warn ("Retrying (empty plan)...")
            console.out.print ()
            continue
         console.fatal ("AI returned an empty plan")

      _validate_plan (plan, commits)
      return plan

   console.muted (last_raw)
   console.fatal ("AI did not return a usable plan")

def _validate_plan (plan: list [dict], commits: list [dict [str, str]]):
   valid_actions = { "keep", "reword", "squash", "drop" }
   full_hashes = { c ["hash"] for c in commits }
   seen = []

   for i, group in enumerate (plan):
      action = group.get ("action")
      if action not in valid_actions:
         console.fatal (f"Group {i}: invalid action '{action}'")

      hashes = group.get ("hashes") or []
      if not hashes:
         console.fatal (f"Group {i}: empty hashes")

      resolved = []
      for h in hashes:
         match = _match_hash (h, full_hashes)
         if not match:
            console.fatal (f"Group {i}: unknown hash {h}")
         resolved.append (match)
      group ["hashes"] = resolved
      seen.extend (resolved)

      if action in { "keep", "drop" } and len (resolved) != 1:
         console.fatal (f"Group {i}: {action} requires exactly one hash")
      if action == "squash" and len (resolved) < 2:
         console.fatal (f"Group {i}: squash requires 2+ hashes")

      if action in { "reword", "squash" }:
         msg = (group.get ("message") or "").strip ()
         if not msg:
            console.fatal (f"Group {i}: {action} requires a message")
         if not validate.commit (msg):
            console.fatal (f"Group {i}: invalid commit message: {msg}")

   expected = [ c ["hash"] for c in commits ]
   missing = [ h [:7] for h in expected if h not in seen ]
   if missing:
      console.fatal (f"Plan missing commits: {', '.join (missing)}")

   if sorted (seen) != sorted (expected):
      extras = [ h [:7] for h in seen if h not in expected ]
      console.fatal (f"Plan has unknown commits: {', '.join (extras)}")

   order = { h: i for i, h in enumerate (expected) }
   last = -1
   for group in plan:
      for h in group ["hashes"]:
         if order [h] < last:
            console.fatal ("Plan reorders commits, not supported")
         last = order [h]

def _match_hash (prefix: str, full: set [str]) -> str:
   for h in full:
      if h.startswith (prefix):
         return h
   return ""

def _show_plan (plan: list [dict], commits: list [dict [str, str]]):
   subjects = { c ["hash"]: c ["subject"] for c in commits }
   lines = []

   for group in plan:
      action = group ["action"]
      first = group ["hashes"] [0] [:7]

      if action == "keep":
         lines.append (f"keep    {first}  {subjects [group ['hashes'] [0]]}")
      elif action == "drop":
         lines.append (f"drop    {first}  {subjects [group ['hashes'] [0]]}")
      elif action == "reword":
         lines.append (f"reword  {first}  {group ['message']}")
      else:
         joined = " ".join (h [:7] for h in group ["hashes"])
         lines.append (f"squash  {joined}")
         lines.append (f"        → {group ['message']}")

   console.items ("Proposed", "\n".join (lines))
   console.out.print ()

def _apply (plan: list [dict], base: str):
   original = git.rev_parse ("HEAD")
   backup_ref = f"refs/imp/backup/tidy-{int (time.time ())}"
   git.update_ref (backup_ref, original)

   try:
      git.reset (base, hard=True)

      for group in plan:
         action = group ["action"]
         hashes = group ["hashes"]

         if action == "drop":
            continue

         if action == "keep":
            git.cherry_pick (hashes [0])
            continue

         for h in hashes:
            git.cherry_pick (h, no_commit=True)
         git.commit (group ["message"])

      git.delete_ref (backup_ref)

   except subprocess.CalledProcessError as e:
      console.err (f"Tidy failed: {e.stderr.strip () if e.stderr else e}")
      console.warn ("Rolling back...")
      git.cherry_pick_abort ()
      git.reset (original, hard=True)
      git.delete_ref (backup_ref)
      raise typer.Exit (1) from None
