import subprocess
from datetime import date
from pathlib import Path

import typer

from imp_git import console, gh, git, version
from imp_git.commands.release import _push_commits, require_tag_available


def _default_floor (new_version: str) -> str:
   """Highest stable tag strictly below the new version — collapsing into
   2.4.0 keeps 2.3.x. Empty when the new version sits at or below every
   stable tag (a renumber-down like 2.3.2 → 2.0.1); the caller then makes
   --since required so the floor is never guessed wrong."""
   target = version.base_tuple (new_version)

   for t in git.tags ():  # newest first
      if "-" in t:
         continue
      base = version.base_tuple (t)
      if base and base < target:
         return t.lstrip ("v")

   return ""

def _victims (floor: tuple [int, int, int], keep: str) -> list [str]:
   """Every v-tag whose base version is strictly above the floor, newest
   first. Non-semver tags and the new version's own tag are left alone."""
   out = []

   for t in git.tags ():
      if t == keep:
         continue
      base = version.base_tuple (t)
      if base and base > floor:
         out.append (t)

   return out

def collapse (
   new_version: str = typer.Argument (..., help="Version the collapsed releases become, e.g. 2.0.1"),
   since: str = typer.Option (
      "",
      "--since",
      "-s",
      help="Keep this version; delete later tags. Defaults to the highest earlier stable tag.",
   ),
   yes: bool = typer.Option (False, "--yes", "-y", help="Skip confirmation"),
   no_push: bool = typer.Option (False, "--no-push", help="Delete + retag locally; leave origin untouched"),
):
   """Consolidate a run of releases into one.

   Deletes every tag above the --since floor — locally, on origin, and their
   GitHub releases — then tags HEAD as <new_version>. Use it to squash or
   renumber a messy release history, e.g. fold v2.1.0…v2.3.2 back into a
   single v2.0.1. Refs only: no commits or code are removed, and the kept
   floor release is left untouched.

   Fetches tags first so it operates on the remote's real state. Manifests
   are synced to <new_version> before tagging, so the tag points at a tree
   whose package.json/pyproject already carries it.
   """

   git.require ()
   git.require_clean ("imp commit first")

   new_version = new_version.lstrip ("v")
   new_tag = f"v{new_version}"

   if version.base_tuple (new_version) is None:
      console.fatal (f"Not a semver version: {new_version}")

   console.spin ("Fetching tags...", git.fetch, tags=True, prune=True)

   require_tag_available (new_version)

   floor = since.lstrip ("v") if since else _default_floor (new_version)

   if not floor:
      console.hint ("pass the last release to keep, e.g. --since 2.0.0")
      console.fatal ("No stable tag below the new version; --since is required")

   floor_tuple = version.base_tuple (floor)

   if floor_tuple is None:
      console.fatal (f"Not a semver version: {floor}")

   victims = _victims (floor_tuple, new_tag)

   if not victims:
      console.hint ("nothing above the floor — use `imp release` for a normal bump")
      console.fatal (f"No tags above v{floor} to collapse")

   head = git.rev_parse ("HEAD") [:8]

   console.header ("Collapse")
   console.items (f"Deleting {len (victims)} tag(s)", "\n".join (victims))
   console.out.print ()
   console.muted (f"Keeping v{floor}")
   console.label (f"→ {new_tag} at {head}")
   console.out.print ()

   if not yes and not console.confirm (f"Collapse into {new_tag}?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   will_push = not no_push and git.remote_exists ()

   if no_push:
      console.muted ("--no-push: keeping changes local")
   elif not git.remote_exists ():
      console.muted ("No remote configured, skipping push")

   # Fold manifests + CHANGELOG.md into the new version so the tag points at
   # a tree that already reflects it. imp owns CHANGELOG.md, so its release
   # sections above the floor collapse into one just like the tags do.
   root    = Path (git.repo_root ())
   changed = version.sync_manifests (root, new_version)

   changelog = root / "CHANGELOG.md"
   if changelog.is_file ():
      before = changelog.read_text ()
      after  = version.consolidate_changelog (before, floor_tuple, new_version, date.today ().isoformat ())
      if after != before:
         changelog.write_text (after)
         changed.append (changelog)

   committed = False
   if changed:
      git.add ([ str (p) for p in changed ])
      git.commit (f"chore: collapse releases into {new_tag}")
      committed = True
      for p in changed:
         console.success (f"Updated {p.relative_to (root)}")

   for t in victims:
      git.tag_delete (t)
   console.success (f"Deleted {len (victims)} local tag(s)")

   git.tag (new_tag)
   console.success (f"Tagged {new_tag}")

   if not will_push:
      console.hint (f"push later: imp push origin {new_tag}")
      return

   try:
      if committed:
         _push_commits ()

      remote = set (git.remote_tags ())
      stale = [ t for t in victims if t in remote ]

      if stale:
         git.push_delete (stale)
         console.success (f"Deleted {len (stale)} remote tag(s)")

      git.push (ref=new_tag)
      console.success (f"Pushed {new_tag}")
   except (subprocess.CalledProcessError, OSError) as e:
      detail = (getattr (e, "stderr", "") or str (e)).strip ()
      console.err (f"Push failed: {detail}")
      raise typer.Exit (1) from None

   if gh.available ():
      removed = sum (gh.release_delete (t) for t in victims)
      if removed:
         console.success (f"Removed {removed} GitHub release(s)")
