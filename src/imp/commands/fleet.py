import os
from pathlib import Path

import typer

from imp import console, git, version
from imp.commands.release import current_version
from imp.commands.ship import ship

def _find_repos (root: Path, max_depth: int) -> list [Path]:
   """Walk directory tree, short-circuiting at each .git."""

   found: list [Path] = []

   def walk (path: Path, depth: int):
      if (path / ".git").is_dir ():
         found.append (path)
         return

      if depth >= max_depth:
         return

      try:
         entries = sorted (path.iterdir ())
      except (PermissionError, OSError):
         return

      for entry in entries:
         if entry.is_dir () and not entry.is_symlink () and not entry.name.startswith ("."):
            walk (entry, depth + 1)

   walk (root, 0)
   return found

def _rel (repo: Path, root: Path) -> str:
   rel = str (repo.relative_to (root))
   if rel in ("", "."):
      return repo.name
   return rel

def _label (repo: Path, root: Path) -> str:
   rel = str (repo.relative_to (root))
   name = repo.name
   if rel in ("", ".") or rel == name:
      return f"{name}  ({rel or '.'})"
   return f"{name}  ({rel})"

def _needs_ship (repo: Path) -> bool:
   """True if the repo has uncommitted changes or untagged commits."""

   original = Path.cwd ()
   os.chdir (repo)
   try:
      if git.diff_names ():
         return True

      tag = git.last_tag ()
      if tag:
         return bool (git.log_oneline (rev_range=f"{tag}..HEAD"))

      return bool (git.log_oneline (count=1))
   finally:
      os.chdir (original)

def _prompt_level (repo_name: str) -> str:
   choice = console.choose (
      f"Version bump for {repo_name}",
      [ "patch", "minor", "major", "skip" ],
   )

   if choice == "skip":
      return ""
   return choice

def _prompt_kind (repo_name: str) -> bool:
   choice = console.choose (
      f"Release type for {repo_name}",
      [ "rc   (pre-release)", "stable" ],
   )

   return choice.startswith ("rc")

def _plan_repo (repo: Path, rel: str, rel_path: str, level: str, rc: bool, stable: bool) -> dict:
   """Gather plan for one repo. Cwd must already be in repo."""

   files = len (git.diff_names ())

   tag = git.last_tag ()
   if tag:
      log = git.log_oneline (rev_range=f"{tag}..HEAD")
   else:
      log = git.log_oneline (count=20)
   commits = len (log.splitlines ()) if log else 0

   repo_level = level or _prompt_level (rel)

   if not repo_level:
      return {
         "path": repo,
         "rel": rel,
         "rel_path": rel_path,
         "skip": True,
         "level": "",
         "current": current_version (),
         "new": "",
         "is_rc": False,
         "files": files,
         "commits": commits,
         "tag": tag,
      }

   if rc:
      is_rc = True
   elif stable:
      is_rc = False
   elif git.branch () != git.base_branch ():
      is_rc = _prompt_kind (rel)
   else:
      is_rc = False

   current = current_version ()
   base_ver = version.bump (current, repo_level)

   if is_rc:
      new_ver = version.next_rc (base_ver, git.rc_tags (base_ver))
   else:
      new_ver = base_ver

   return {
      "path": repo,
      "rel": rel,
      "rel_path": rel_path,
      "skip": False,
      "level": repo_level,
      "current": current,
      "new": new_ver,
      "is_rc": is_rc,
      "files": files,
      "commits": commits,
      "tag": tag,
   }

def _print_plan (plan: dict):
   console.label (f"▸ {plan ['rel']}")
   console.item (f"path:    {plan ['rel_path']}")

   if plan ["skip"]:
      console.item ("status:  skip")
      return

   kind = "rc" if plan ["is_rc"] else "stable"
   since = plan ["tag"] or "beginning"
   console.item (f"current: v{plan ['current']}")
   console.item (f"changes: {plan ['files']} file(s), {plan ['commits']} commit(s) since {since}")
   console.item (f"bump:    {plan ['level']} → v{plan ['new']} ({kind})")

def fleet (
   path: Path = typer.Argument (Path ("."), help="Directory to scan for git repos"),
   patch: bool = typer.Option (False, "--patch", help="Bump patch on every repo"),
   minor: bool = typer.Option (False, "--minor", help="Bump minor on every repo"),
   major: bool = typer.Option (False, "--major", help="Bump major on every repo"),
   rc: bool = typer.Option (False, "--rc", help="Tag every repo as pre-release"),
   stable: bool = typer.Option (False, "--stable", help="Tag every repo as stable"),
   squash: bool = typer.Option (False, "--squash", help="Squash split commits into a single release commit"),
   depth: int = typer.Option (5, "--depth", "-d", help="Max directory depth to scan"),
   dry_run: bool = typer.Option (False, "--dry-run", help="List repos without shipping"),
):
   """Ship every dirty git repository under a directory.

   Recursively scans for git repositories and runs ship on each one that
   has uncommitted changes or untagged commits. Clean repos are skipped.
   Failures in one repo do not stop the rest; a summary is printed at the
   end. Flags apply to every repo; when omitted, fleet prompts per-repo.
   """

   if rc and stable:
      console.fatal ("--rc and --stable are mutually exclusive")

   if sum ([ patch, minor, major ]) > 1:
      console.fatal ("--patch, --minor, --major are mutually exclusive")

   level = ""
   if major:
      level = "major"
   elif minor:
      level = "minor"
   elif patch:
      level = "patch"

   root = path.resolve ()

   if not root.is_dir ():
      console.fatal (f"Not a directory: {root}")

   console.header ("Fleet")
   console.muted (f"Scanning {root} (depth {depth})")
   console.out.print ()

   repos = _find_repos (root, depth)

   if not repos:
      console.muted ("No git repositories found")
      return

   dirty = [ r for r in repos if _needs_ship (r) ]
   clean = len (repos) - len (dirty)

   if clean:
      console.muted (f"{clean} clean, skipping")

   if not dirty:
      console.success ("Nothing to ship")
      return

   console.items (
      f"{len (dirty)} repo(s) to ship",
      "\n".join (_label (r, root) for r in dirty),
   )
   console.out.print ()

   original = Path.cwd ()
   plans: list [dict] = []

   for repo in dirty:
      os.chdir (repo)
      plans.append (_plan_repo (
         repo,
         _rel (repo, root),
         str (repo.relative_to (root)),
         level, rc, stable,
      ))

   os.chdir (original)

   console.divider ()
   console.header ("Plan")

   for plan in plans:
      _print_plan (plan)
      console.out.print ()

   to_ship = [ p for p in plans if not p ["skip"] ]

   if not to_ship:
      console.muted ("All repos skipped, nothing to do")
      return

   if dry_run:
      console.muted ("Dry run, nothing shipped")
      return

   console.divider ()

   if not console.confirm (f"Ship {len (to_ship)} repo(s)?"):
      console.muted ("Cancelled")
      return

   results: list [tuple [str, str]] = []

   for plan in plans:
      rel = plan ["rel"]

      if plan ["skip"]:
         results.append ((rel, "skipped"))
         continue

      console.divider ()
      console.label (f"▸ {rel}")

      os.chdir (plan ["path"])

      try:
         ship (
            patch=(plan ["level"] == "patch"),
            minor=(plan ["level"] == "minor"),
            major=(plan ["level"] == "major"),
            rc=plan ["is_rc"],
            stable=not plan ["is_rc"],
            squash=squash,
            whisper="",
         )
         kind = "rc" if plan ["is_rc"] else "stable"
         results.append ((rel, f"shipped v{plan ['new']} ({plan ['level']} {kind})"))
      except typer.Exit as e:
         code = getattr (e, "exit_code", 0)
         results.append ((rel, "no-op" if code == 0 else "failed"))
      except Exception as e:
         results.append ((rel, f"error: {e}"))

   os.chdir (original)

   console.divider ()
   console.header ("Summary")

   for rel, status in results:
      console.item (f"{rel}: {status}")
