from pathlib import Path
from typing import Annotated

import typer

from imp_git import console, features, fingerprint, git, hygiene, result, runtime, state


def _file_style (code: str) -> str:
   if code in ("M ", "AM"):
      return "green"
   if code == " M" or code == "MM":
      return "yellow"
   if code.strip () == "D":
      return "red"
   if code.startswith ("A"):
      return "green"
   if code.startswith ("R"):
      return f"{console.theme.accent}"
   if code == "??":
      return "dim"
   return "default"

def status (
   json_output: Annotated [bool, typer.Option ("--json", help="Emit a versioned JSON result")] = False,
):
   """Show repository overview.

   Displays the current branch, file changes with line-level stats,
   commits since the last tag, worktrees, and the last release version.
   Suggests a next action based on the current state.
   """

   git.require ()

   name = git.repo_name ()
   b = git.branch ()
   tag = git.last_tag ()
   managed = features.all ()
   hygiene_warnings, hygiene_blockers = hygiene.inspect (git.changed_paths (all_changes=True))
   try:
      selected = features.active ()
   except state.StateError:
      selected = None

   data = {
      "repository": name,
      "branch": b,
      "head_oid": git.rev_parse ("HEAD"),
      "source_fingerprint": fingerprint.repository (),
      "changes": git.status_short ().splitlines (),
      "active": {
         "feature_id": selected.get ("feature_id"),
         "generation": selected.get ("generation"),
         "path": selected.get ("path"),
      } if selected else None,
      "features": managed,
      "hygiene": { "blockers": hygiene_blockers, "warnings": hygiene_warnings },
      "last_release": tag or None,
   }
   if json_output or runtime.options.json:
      return result.emit ("imp.status.v1", "imp status", data, json_output=True)

   console.header (name)

   if selected:
      console.label ("Active source")
      console.item (str (selected.get ("feature_id") or "trunk"))
      console.item (str (selected ["path"]))
      console.out.print ()

   if managed:
      rows = []
      for feature in managed:
         claim = feature.get ("claim", {})
         rows.append ([
            str (feature ["name"]),
            str (feature ["branch"]),
            str (claim.get ("held_by", "unclaimed") if claim else "unclaimed"),
            str (feature ["path"]),
         ])
      console.label ("Features")
      console.table ([ "Feature", "Branch", "Writer", "Path" ], rows)
      console.out.print ()

   console.label ("Branch")
   sync_info = ""
   if git.has_upstream ():
      ahead = git.count_ahead ()
      behind = git.count_behind ()
      if ahead == 0 and behind == 0:
         sync_info = " [muted](up to date)[/muted]"
      else:
         parts = []
         if ahead > 0:
            parts.append (f"[green]{ahead} ahead[/green]")
         if behind > 0:
            parts.append (f"[yellow]{behind} behind[/yellow]")
         sync_info = f" ({', '.join (parts)})"
   console.out.print (f"  [muted]{b}[/muted]{sync_info}")
   console.out.print ()

   changes = git.status_short ()
   if changes:
      numstat_raw = git.diff_numstat ()
      stats = {}
      for line in numstat_raw.splitlines ():
         parts = line.split ("\t")
         if len (parts) == 3:
            added, removed, path = parts
            stats [path] = (added, removed)

      console.label ("Changes")
      for line in changes.splitlines ():
         if len (line) < 4:
            continue
         code = line [:2]
         path = line [2:].lstrip (" ")
         style = _file_style (code)

         stat_str = ""
         if path in stats:
            a, r = stats [path]
            stat_str = f" [green]+{a}[/green] [red]-{r}[/red]"

         label = code.strip ().replace ("??", "?")
         console.out.print (f"  [{style}]{label}[/{style}]  {path}{stat_str}")
      console.out.print ()

   for warning in hygiene_warnings:
      console.warn (warning)
   for blocker in hygiene_blockers:
      console.err (blocker)

   if tag:
      unpushed = git.log_oneline (rev_range=f"{tag}..HEAD")
   else:
      unpushed = git.log_oneline (count=10)

   if unpushed:
      count = len (unpushed.splitlines ())
      console.items (f"Commits since {tag or 'start'} ({count})", unpushed)
      console.out.print ()

   wt = git.worktree_list ()
   wt_lines = wt.splitlines () if wt else []
   if len (wt_lines) > 1:
      console.label ("Worktrees")
      cwd = str (Path.cwd ())
      for line in wt_lines:
         if line.startswith (cwd + " "):
            console.item (f"{line} (here)")
         else:
            console.item (line)
      console.out.print ()

   if tag:
      console.muted (f"Last release: {tag}")

   if changes:
      console.hint ("imp commit to plan local commits")
   elif unpushed:
      console.hint ("imp ship when trunk is ready")
   else:
      console.hint ("make changes, then imp commit")

   return data
