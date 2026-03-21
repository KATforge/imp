from imp import console, git


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


def status ():
   """Show repository overview.

   Displays the current branch, file changes with line-level stats,
   commits since the last tag, worktrees, and the last release version.
   Suggests a next action based on the current state.
   """

   git.require ()

   name = git.repo_name ()
   b = git.branch ()
   tag = git.last_tag ()

   console.header (name)

   console.label ("Branch")
   console.item (b)
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

         console.out.print (f"  [{style}]{code.strip ()}[/{style}]  {path}{stat_str}")
      console.out.print ()

   if tag:
      unpushed = git.log_oneline (rev_range=f"{tag}..HEAD")
   else:
      unpushed = git.log_oneline (count=10)

   if unpushed:
      count = len (unpushed.splitlines ())
      console.items (f"Commits since {tag or 'start'} ({count})", unpushed)

   wt = git.worktree_list ()
   wt_lines = wt.splitlines () if wt else []
   if len (wt_lines) > 1:
      console.label ("Worktrees")
      from pathlib import Path
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
      console.hint ("git add <files>, then imp commit")
   elif unpushed:
      console.hint ("imp release to ship")
   else:
      console.hint ("make changes, then imp commit")
