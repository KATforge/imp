import datetime
import json

import typer

from imp import ai, console, git, prompts

def standup (
   since: str = typer.Option ("", "--since", "-s", help="Custom time range (e.g. 'last monday')"),
   author: str = typer.Option ("", "--author", "-a", help="Filter by author (default: current git user)"),
   as_json: bool = typer.Option (False, "--json", help="Machine-readable JSON output"),
   as_markdown: bool = typer.Option (False, "--markdown", "-m", help="Markdown for Slack/Plane paste"),
):
   """Summarize recent commits as a standup narrative.

   Default range is yesterday (or last working day on Monday). AI groups
   commits by theme and cites hashes. Use --json or --markdown for
   non-interactive consumers.
   """

   git.require ()

   if as_json and as_markdown:
      console.fatal ("--json and --markdown are mutually exclusive")

   resolved_since = since or _default_since ()
   who = author or git.user_email () or ""

   entries = git.log_by_author (who, since=resolved_since) if who else _log_all_since (resolved_since)

   if not entries:
      if as_json:
         console.out.print (json.dumps ({ "since": resolved_since, "author": who, "summary": "", "commits": [] }))
         return
      console.header ("Standup")
      console.muted (f"No commits since {resolved_since}" + (f" by {who}" if who else ""))
      raise typer.Exit (0)

   lines = "\n".join (f"{e ['hash'] [:12]} {e ['date']} {e ['subject']}" for e in entries)

   summary = console.spin (
      "Summarizing...",
      ai.smart,
      prompts.standup (lines, author=who, since=resolved_since),
      False,
   )
   summary = summary.strip ()

   if as_json:
      payload = {
         "since": resolved_since,
         "author": who,
         "commit_count": len (entries),
         "summary": summary,
         "commits": entries,
      }
      console.out.print (json.dumps (payload, indent=2))
      return

   if as_markdown:
      console.out.print (summary)
      return

   console.header ("Standup")
   console.label ("Range")
   console.item (f"since: {resolved_since}")
   if who:
      console.item (f"author: {who}")
   console.item (f"commits: {len (entries)}")
   console.out.print ()
   console.divider ()
   console.md (summary)
   console.divider ()

def _default_since () -> str:
   today = datetime.date.today ()
   if today.weekday () == 0:
      delta = 3
   else:
      delta = 1
   target = today - datetime.timedelta (days=delta)
   return target.isoformat ()

def _log_all_since (since: str) -> list [dict [str, str]]:
   entries = git.log_since (since)
   resolved: list [dict [str, str]] = []
   for e in entries:
      stamp = git.show (e ["hash"], fmt="%ai").split () [0] if e.get ("hash") else ""
      resolved.append ({ "hash": e ["hash"], "subject": e ["subject"], "date": stamp })
   return resolved
