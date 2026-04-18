import os
from pathlib import Path

import typer

from imp import console, git
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
      "\n".join (str (r.relative_to (root)) for r in dirty),
   )
   console.out.print ()

   if dry_run:
      console.muted ("Dry run, nothing shipped")
      return

   results: list [tuple [str, str]] = []
   original = Path.cwd ()

   for repo in dirty:
      rel = str (repo.relative_to (root)) or repo.name
      console.divider ()
      console.label (f"▸ {rel}")
      console.out.print ()

      os.chdir (repo)

      repo_level = level or _prompt_level (rel)

      if not repo_level:
         results.append ((rel, "skipped"))
         continue

      try:
         ship (
            patch=(repo_level == "patch"),
            minor=(repo_level == "minor"),
            major=(repo_level == "major"),
            rc=rc,
            stable=stable,
            squash=squash,
            whisper="",
         )
         results.append ((rel, f"shipped ({repo_level})"))
      except typer.Exit as e:
         code = getattr (e, "exit_code", 0)
         results.append ((rel, "no-op" if code == 0 else "failed"))
      except Exception as e:
         results.append ((rel, f"error: {e}"))

   os.chdir (original)

   console.out.print ()
   console.divider ()
   console.header ("Summary")

   for rel, status in results:
      console.item (f"{rel}: {status}")
