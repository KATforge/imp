import json

import typer

from imp import ai, console, git, prompts

def rescue (
   hint: list [str] | None = typer.Argument (None, help="Optional topic to filter candidates"),
   since: str = typer.Option ("", "--since", "-s", help="Narrow time window (e.g. '2h ago')"),
   limit: int = typer.Option (10, "--limit", "-n", help="Max candidates to show"),
):
   """Find lost work in reflog and dangling commits.

   Walks the reflog plus any orphaned commits, asks AI to rank them by
   likely value, and prints recovery suggestions. Never executes recovery
   commands; the human runs them.
   """

   git.require ()

   console.header ("Rescue")

   hint_str = " ".join (hint) if hint else ""

   candidates = _collect (since)

   if not candidates:
      console.muted ("No reflog or dangling candidates found")
      raise typer.Exit (0)

   console.muted (f"Scanning {len (candidates)} candidates...")

   ranked = _rank (candidates, hint_str)
   if not ranked:
      console.muted ("No promising candidates")
      raise typer.Exit (0)

   ranked = ranked [:limit]
   _show (ranked, candidates)

   labels = []
   for r in ranked:
      meta = candidates.get (r ["sha"], {})
      subject = meta.get ("subject", "(no subject)")
      labels.append (f"{r ['sha'] [:7]}  ({r ['score']:>3})  {subject [:60]}")

   labels.append ("Cancel")

   choice = console.choose ("Inspect which?", labels)
   if choice == "Cancel":
      console.muted ("Cancelled")
      raise typer.Exit (0)

   chosen_sha = choice.split () [0]
   full = _expand (chosen_sha, candidates)
   if not full:
      console.fatal (f"Cannot expand {chosen_sha}")

   _recovery_suggestions (full, candidates [full])

def _collect (since: str) -> dict [str, dict [str, str]]:
   candidates: dict [str, dict [str, str]] = {}

   for entry in git.reflog (since=since):
      sha = entry ["hash"]
      if not sha or sha in candidates:
         continue
      subject = git.show_oneline (sha)
      if not subject:
         continue
      candidates [sha] = {
         "sha": sha,
         "ref": entry ["ref"],
         "message": entry ["message"],
         "age": entry ["age"],
         "subject": subject.split (" ", 1) [1] if " " in subject else subject,
         "stat": git.show_stat (sha),
         "source": "reflog",
      }

   for sha in git.dangling_commits ():
      if sha in candidates:
         continue
      subject = git.show_oneline (sha)
      if not subject:
         continue
      candidates [sha] = {
         "sha": sha,
         "ref": "(dangling)",
         "message": "",
         "age": git.show_age (sha),
         "subject": subject.split (" ", 1) [1] if " " in subject else subject,
         "stat": git.show_stat (sha),
         "source": "dangling",
      }

   return candidates

def _rank (candidates: dict [str, dict [str, str]], hint: str) -> list [dict]:
   blocks = []
   for sha, meta in candidates.items ():
      stat_first = meta ["stat"].splitlines () [-1] if meta ["stat"] else "(no stat)"
      blocks.append (
         f"sha: {sha [:12]}\n"
         f"age: {meta ['age']}\n"
         f"source: {meta ['source']}\n"
         f"subject: {meta ['subject']}\n"
         f"stat: {stat_first}"
      )

   prompt = prompts.rescue_rank ("\n\n".join (blocks), hint)
   raw = ai.strip_fences (ai.smart (prompt))

   try:
      data = json.loads (raw)
   except json.JSONDecodeError:
      console.muted (raw)
      console.fatal ("AI did not return valid JSON")

   if not isinstance (data, list):
      console.muted (raw)
      console.fatal ("AI did not return a JSON array")

   resolved: list [dict] = []
   for entry in data:
      if not isinstance (entry, dict):
         continue
      sha = _expand (entry.get ("sha", ""), candidates)
      if not sha:
         continue
      resolved.append ({
         "sha": sha,
         "score": int (entry.get ("score", 0)),
         "what": entry.get ("what", ""),
      })

   return resolved

def _expand (prefix: str, candidates: dict [str, dict [str, str]]) -> str:
   if not prefix:
      return ""
   if prefix in candidates:
      return prefix
   for sha in candidates:
      if sha.startswith (prefix):
         return sha
   return ""

def _show (ranked: list [dict], candidates: dict [str, dict [str, str]]):
   console.divider ()
   for i, r in enumerate (ranked, 1):
      meta = candidates [r ["sha"]]
      console.label (f"{i}. {r ['sha'] [:12]}  ({r ['score']}/100)")
      console.item (f"ref:     {meta ['ref']}  ({meta ['source']})")
      console.item (f"age:     {meta ['age']}")
      console.item (f"subject: {meta ['subject']}")
      if r ["what"]:
         console.item (f"what:    {r ['what']}")
   console.divider ()

def _recovery_suggestions (sha: str, meta: dict [str, str]):
   console.out.print ()
   console.label ("Recovery options (run yourself)")
   console.item (f"inspect:       git show {sha [:12]}")
   console.item (f"branch from:   git branch rescued-{sha [:7]} {sha}")
   console.item (f"cherry-pick:   git cherry-pick {sha}")
   console.item (f"hard reset:    git reset --hard {sha}   (DESTRUCTIVE)")
   console.out.print ()
   console.hint ("imp will not run these; copy the one you want")
