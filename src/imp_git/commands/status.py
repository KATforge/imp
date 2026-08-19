from pathlib import Path

from imp_git import console, features, fingerprint, git, hygiene, result, roster, runtime, workspace


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
   "open": "green",
   "dirty": "yellow",
   "branch-only": "red",
}


def _condition (value: str) -> str:
   style = _CONDITION_STYLE.get (value, "default")

   return f"[{style}]{value}[/{style}]"


def _show_roster (entries: list [dict]):
   if not entries:
      return
   console.label ("Features")
   console.table (
      [ "Feature", "Repositories", "State", "Age" ],
      [
         [
            str (entry ["name"]),
            " ".join (entry ["repositories"]),
            _condition (str (entry ["condition"])),
            str (entry ["age"]),
         ]
         for entry in entries
      ],
   )
   console.out.print ()
   console.hint ("imp done to integrate, imp cleanup to flatten")


def _workspace_status (json_output: bool):
   value = workspace.here ()
   entries = roster.collect (value)
   repositories = workspace.repositories (value)
   data = {
      "workspace": value ["name"],
      "root": value ["root"],
      "repositories": sorted (repositories),
      "features": entries,
      "members": roster.repositories (value),
   }
   if json_output:
      return result.emit ("imp.roster.v3", "imp status", data, json_output=True)
   console.header (str (value ["name"]))
   _show_members (data ["members"])
   _show_roster (entries)

   return data


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


def _show_features (managed: list [dict]):
   if not managed:
      return
   console.label ("Features")
   console.table (
      [ "Feature", "Branch", "State", "Path" ],
      [
         [
            str (feature ["name"]),
            str (feature ["branch"]),
            _condition ("open" if feature ["worktree_state"] == "live" else "branch-only"),
            str (feature ["path"]),
         ]
         for feature in managed
      ],
   )
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


def _unreviewed () -> str:
   if not git.remote_exists ():
      return ""
   trunk = git.base_branch ()
   remote = f"origin/{trunk}"
   if not git.rev_parse (remote) or git.branch () != trunk:
      return ""
   return git.log_oneline (rev_range=f"{remote}..{trunk}")


def _hint (changes: str, unreviewed: str, unpushed: str):
   if changes:
      console.hint ("imp commit to plan local commits")
   elif unreviewed:
      console.hint ("imp review to inspect unpushed trunk, then push")
   elif unpushed:
      console.hint ("imp release when trunk is ready")
   else:
      console.hint ("make changes, then imp commit")


def status ():
   """Show the current repository or workspace at a glance, with the next step.

   From a directory of checkouts: every member repository, its drift against origin,
   and every open feature grouped by name. From inside a repository: open features,
   the current branch and its sync state, file changes with line stats, commits since
   the last release, and worktrees. Ends with the most useful next imp command.
   Deterministic; sends nothing to AI.
   """

   json_output = runtime.options.json

   if not git.succeeds ("rev-parse", "--git-dir") and workspace.here ():
      return _workspace_status (json_output)

   git.require ()

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
      "hygiene": { "blockers": [], "warnings": hygiene_warnings },
      "last_release": tag or None,
   }
   if json_output:
      return result.emit ("imp.status.v5", "imp status", data, json_output=True)

   console.header (name)
   _show_features (managed)
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

   _hint (changes, _unreviewed (), unpushed)

   return data
