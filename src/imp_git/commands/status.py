from pathlib import Path

from imp_git import console, features, fingerprint, git, hygiene, result, roster, runtime, spans, state, workspace


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


_CONDITION_STYLE = {
   roster.READY: "green",
   roster.CONFLICT: "red",
   roster.CHECKS: "yellow",
   roster.DIRTY: "yellow",
   roster.EMPTY: "muted",
   roster.BROKEN: "red",
}


def _condition (value: str) -> str:
   style = _CONDITION_STYLE.get (value, "default")

   return f"[{style}]{value}[/{style}]"


def _show_roster (value: dict, entries: list [dict]):
   if not entries:
      return
   console.label ("Features")
   console.table (
      [ "Feature", "Repositories", "State", "Writer", "Age" ],
      [
         [
            str (entry ["name"]),
            " ".join (entry ["repositories"]),
            _condition (str (entry ["condition"])),
            ", ".join (writer.rpartition (":") [0].removeprefix ("actor:") for writer in entry ["writers"]),
            str (entry ["age"]),
         ]
         for entry in entries
      ],
   )
   ready = len (roster.promotable (entries))
   console.out.print ()
   console.muted (f"{ready} of {len (entries)} ready")
   if ready:
      console.hint ("imp done to promote")


def _workspace_status (json_output: bool):
   value = workspace.here ()
   entries = roster.collect (value)
   repositories = workspace.repositories (value)
   data = {
      "workspace": value ["name"],
      "root": value ["root"],
      "repositories": sorted (repositories),
      "features": entries,
      "interrupted": roster.interrupted (value),
      "members": roster.repositories (value),
   }
   if json_output:
      return result.emit ("imp.roster.v1", "imp status", data, json_output=True)
   console.header (str (value ["name"]))
   _show_members (data ["members"])
   _show_roster (value, entries)
   _show_workspace_interrupted (data ["interrupted"])

   return data


def _show_interrupted (values: list [dict]):
   if not values:
      return
   console.label ("Interrupted")
   console.table (
      [ "Command", "Error", "Resume with" ],
      [
         [
            str (record.get ("command", "")),
            str (record.get ("error", "")),
            str (record.get ("next", "")),
         ]
         for record in values
      ],
   )
   console.out.print ()


def _drift (member: dict) -> str:
   if not member ["tracked"]:
      return "untracked"
   parts = []
   if member ["ahead"]:
      parts.append (f"[green]{member ['ahead']} ahead[/green]")
   if member ["behind"]:
      parts.append (f"[yellow]{member ['behind']} behind[/yellow]")

   return ", ".join (parts) or "[muted]synced[/muted]"


def _show_members (values: list [dict]):
   if not values:
      return
   console.label ("Repositories")
   console.table (
      [ "Repository", "Branch", "Remote", "Dirty", "Worktrees" ],
      [
         [
            str (member ["alias"]),
            str (member ["branch"]),
            _drift (member),
            f"[yellow]{member ['dirty']}[/yellow]" if member ["dirty"] else "",
            str (member ["worktrees"]) if member ["worktrees"] else "",
         ]
         for member in values
      ],
   )
   console.out.print ()


def _show_workspace_interrupted (values: list [dict]):
   if not values:
      return
   console.out.print ()
   console.label ("Interrupted")
   console.table (
      [ "Repository", "Command", "Error" ],
      [
         [ str (record ["alias"]), str (record.get ("command", "")), str (record.get ("error", "")) ]
         for record in values
      ],
   )


def _spans () -> list [dict]:
   value = workspace.here ()

   return spans.all (value) if value else []


def _show_spans (values: list [dict]):
   if not values:
      return
   console.label ("Spanning features")
   console.table (
      [ "Feature", "Repositories" ],
      [ [ str (span ["name"]), ", ".join (sorted (span ["members"])) ] for span in values ],
   )
   console.out.print ()


def _show_features (managed: list [dict]):
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

):
   """Show repository overview.

   Displays the current branch, file changes with line-level stats,
   commits since the last tag, worktrees, and the last release version.
   Suggests a next action based on the current state.
   """

   json_output = runtime.options.json

   if not git.succeeds ("rev-parse", "--git-dir") and workspace.here ():
      return _workspace_status (json_output)

   git.require ()

   state.tidy ()

   name = git.repo_name ()
   branch = git.branch ()
   tag = git.last_tag ()
   managed = features.all ()
   changes = git.status_short ()
   hygiene_warnings = hygiene.inspect (git.changed_paths (all_changes=True))

   data = {
      "repository": name,
      "branch": branch,
      "head_oid": git.rev_parse ("HEAD"),
      "source_fingerprint": fingerprint.repository (),
      "changes": changes.splitlines (),
      "features": managed,
      "interrupted": state.recoveries (),
      "spans": _spans (),
      "hygiene": { "blockers": [], "warnings": hygiene_warnings },
      "last_release": tag or None,
   }
   if json_output:
      return result.emit ("imp.status.v2", "imp status", data, json_output=True)

   console.header (name)
   _show_features (managed)
   _show_spans (data ["spans"])
   _show_interrupted (data ["interrupted"])
   console.label ("Branch")
   console.out.print (f"  [muted]{branch}[/muted]{_sync ()}")
   console.out.print ()
   _show_changes (changes)

   for warning in hygiene_warnings:
      console.warn (warning)

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
      console.hint ("imp release when trunk is ready")
   else:
      console.hint ("make changes, then imp commit")

   return data
