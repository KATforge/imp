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


def _active () -> dict | None:
   try:
      return features.active ()
   except state.StateError:
      return None


def _sync () -> str:
   if not git.has_upstream ():
      return ""
   ahead = git.count_ahead ()
   behind = git.count_behind ()
   if not ahead and not behind:
      return " [muted](up to date)[/muted]"
   parts = []
   if ahead:
      parts.append (f"[green]{ahead} ahead[/green]")
   if behind:
      parts.append (f"[yellow]{behind} behind[/yellow]")
   return f" ({', '.join (parts)})"


def _stats () -> dict [str, tuple [str, str]]:
   values = {}
   for line in git.diff_numstat ().splitlines ():
      parts = line.split ("\t")
      if len (parts) == 3:
         added, removed, path = parts
         values [path] = (added, removed)
   return values


def _show_source (selected: dict | None, managed: list [dict]):
   if selected:
      console.label ("Active source")
      console.item (str (selected.get ("feature_id") or "trunk"))
      console.item (str (selected ["path"]))
      console.out.print ()
   if not managed:
      return
   rows = []
   for feature in managed:
      claim = feature.get ("claim", {})
      writer = claim.get ("held_by", "unclaimed") if claim else "unclaimed"
      rows.append ([ str (feature ["name"]), str (feature ["branch"]), str (writer), str (feature ["path"]) ])
   console.label ("Features")
   console.table ([ "Feature", "Branch", "Writer", "Path" ], rows)
   console.out.print ()


def _show_changes (changes: str):
   if not changes:
      return
   stats = _stats ()
   console.label ("Changes")
   for line in changes.splitlines ():
      if len (line) < 4:
         continue
      code = line [:2]
      path = line [2:].lstrip (" ")
      added, removed = stats.get (path, ("", ""))
      summary = f" [green]+{added}[/green] [red]-{removed}[/red]" if added else ""
      label = code.strip ().replace ("??", "?")
      style = _file_style (code)
      console.out.print (f"  [{style}]{label}[/{style}]  {path}{summary}")
   console.out.print ()


def _show_worktrees ():
   lines = git.worktree_list ().splitlines ()
   if len (lines) < 2:
      return
   console.label ("Worktrees")
   current = str (Path.cwd ()) + " "
   for line in lines:
      console.item (f"{line} (here)" if line.startswith (current) else line)
   console.out.print ()

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
   branch = git.branch ()
   tag = git.last_tag ()
   managed = features.all ()
   changes = git.status_short ()
   hygiene_warnings, hygiene_blockers = hygiene.inspect (git.changed_paths (all_changes=True))
   selected = _active ()

   data = {
      "repository": name,
      "branch": branch,
      "head_oid": git.rev_parse ("HEAD"),
      "source_fingerprint": fingerprint.repository (),
      "changes": changes.splitlines (),
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
   _show_source (selected, managed)
   console.label ("Branch")
   console.out.print (f"  [muted]{branch}[/muted]{_sync ()}")
   console.out.print ()
   _show_changes (changes)

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

   _show_worktrees ()

   if tag:
      console.muted (f"Last release: {tag}")

   if changes:
      console.hint ("imp commit to plan local commits")
   elif unpushed:
      console.hint ("imp ship when trunk is ready")
   else:
      console.hint ("make changes, then imp commit")

   return data
