import subprocess
from datetime import date
from pathlib import Path

import typer

from imp import console, gh, git, version

def _error_detail (e: Exception) -> str:
   return (getattr (e, "stderr", "") or str (e)).strip ()

def rollback (
   ver: str,
   original_head: str,
   changelog_path: Path,
   original_changelog: str,
   committed: bool,
):
   console.warn ("Rolling back...")
   git.tag_delete (f"v{ver}")
   if committed:
      git.reset (original_head, hard=True)
   if original_changelog:
      changelog_path.write_text (original_changelog)
   elif changelog_path.is_file ():
      changelog_path.unlink ()
   console.err ("Release failed")

def require_tag_available (ver: str):
   if git.tag_exists (f"v{ver}"):
      console.hint (f"pick a different version, or: git tag -d v{ver}")
      console.fatal (f"Tag v{ver} already exists")

def subjects_since (tag: str, count: int = 20) -> str:
   if tag:
      return git.log_subjects (rev_range=f"{tag}..HEAD")
   return git.log_subjects (count=count)

def push_release (ver: str, notes: str, force_lease: bool = False):
   if git.has_upstream ():
      git.push (force_lease=force_lease)
   else:
      b = git.branch ()
      git.push (set_upstream=True, target=b)

   git.push (ref=f"v{ver}")
   console.success ("Pushed to origin")

   if gh.available ():
      if gh.release_create (ver, notes):
         console.success ("Created GitHub release")
      else:
         console.muted ("GitHub release skipped (gh auth or repo issue)")

def _squash_commits (tag: str, summary: str, changelog_path: str, count: int) -> bool:
   can_squash = False
   if tag:
      if git.has_upstream ():
         unpushed = git.log_oneline (rev_range="@{u}..HEAD")
         if unpushed:
            can_squash = True
      else:
         can_squash = True

   if can_squash:
      git.reset (tag, soft=True)
      git.stage ()
      git.commit (summary)
      console.success (f"Squashed {count} commits")
   else:
      git.add ([ str (changelog_path) ])
      git.commit (summary)
      if tag:
         console.muted ("Commits already pushed, skipped squash")

   return can_squash

def release_scope () -> tuple [str, str, int]:
   tag = git.last_tag ()

   log = ""
   if tag:
      log = git.log_oneline (rev_range=f"{tag}..HEAD")

   if not log:
      log = git.log_oneline (count=20)
      tag = ""

   if not log:
      console.muted ("No commits to release")
      raise typer.Exit (0)

   return tag, log, len (log.splitlines ())

def current_version () -> str:
   highest = git.highest_tag (stable=True)
   current = highest.lstrip ("v") if highest else "0.0.0"

   return current or "0.0.0"

def _semver_bumps (current: str) -> tuple [str, str, str]:
   return (
      version.bump (current, "patch"),
      version.bump (current, "minor"),
      version.bump (current, "major"),
   )

def do_release (
   new_version: str,
   tag: str,
   count: int,
   will_push: bool = True,
   squash: bool = True,
):
   subjects = subjects_since (tag, count)

   entry = version.changelog_from_commits (subjects)
   summary = f"chore: release v{new_version}"
   today = date.today ().isoformat ()
   new_entry = f"## [{new_version}] - {today}\n\n{entry}"

   root = git.repo_root ()
   changelog_path = Path (root) / "CHANGELOG.md"

   original_head = git.rev_parse ("HEAD")
   original_changelog = ""
   if changelog_path.is_file ():
      original_changelog = changelog_path.read_text ()

   committed = False
   can_squash = False

   try:
      version.write_changelog (changelog_path, new_entry)
      console.success ("Updated CHANGELOG.md")

      if squash:
         can_squash = _squash_commits (tag, summary, changelog_path, count)
      else:
         git.add ([ str (changelog_path) ])
         git.commit (summary)

      committed = True

      git.tag (f"v{new_version}")
      console.success (f"Tagged v{new_version}")

   except (subprocess.CalledProcessError, OSError) as e:
      console.err (f"Release failed: {_error_detail (e)}")
      rollback (
         new_version, original_head, changelog_path,
         original_changelog, committed,
      )
      raise typer.Exit (1) from None

   if will_push:
      try:
         push_release (new_version, entry, force_lease=can_squash)
      except (subprocess.CalledProcessError, OSError) as e:
         console.err (f"Push failed: {_error_detail (e)}")
         raise typer.Exit (1) from None

def do_release_rc (level: str):
   current = current_version ()
   base_ver = version.bump (current, level)
   new_ver = version.next_rc (base_ver, git.rc_tags (base_ver))

   require_tag_available (new_ver)

   git.tag (f"v{new_ver}")
   console.success (f"Tagged v{new_ver}")

   if git.remote_exists ():
      if git.has_upstream ():
         git.push ()
      else:
         b = git.branch ()
         git.push (set_upstream=True, target=b)

      git.push (ref=f"v{new_ver}")
      console.success ("Pushed to origin")
   else:
      console.muted ("No remote, skipped push")

def release_rc (level: str = ""):
   tag, log, count = release_scope ()

   console.header ("Pre-release")
   console.items (f"Commits since {tag or 'beginning'}", log)
   console.out.print ()

   current = current_version ()

   patch_ver, minor_ver, major_ver = _semver_bumps (current)

   patch_rc = version.next_rc (patch_ver, git.rc_tags (patch_ver))
   minor_rc = version.next_rc (minor_ver, git.rc_tags (minor_ver))
   major_rc = version.next_rc (major_ver, git.rc_tags (major_ver))

   if level == "patch":
      new_ver = patch_rc
   elif level == "minor":
      new_ver = minor_rc
   elif level == "major":
      new_ver = major_rc
   else:
      console.muted (f"Current stable: {current}")
      console.out.print ()

      choice = console.choose (
         "Version target",
         [
            f"patch  {patch_rc}",
            f"minor  {minor_rc}",
            f"major  {major_rc}",
            "quit",
         ],
      )

      if choice.startswith ("patch"):
         new_ver = patch_rc
      elif choice.startswith ("minor"):
         new_ver = minor_rc
      elif choice.startswith ("major"):
         new_ver = major_rc
      else:
         console.muted ("Cancelled")
         raise typer.Exit (0)

   require_tag_available (new_ver)

   console.label (f"v{new_ver}")

   if not console.confirm (f"Tag v{new_ver}?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   git.tag (f"v{new_ver}")
   console.success (f"Tagged v{new_ver}")

   if git.remote_exists () and console.confirm ("Push tag?"):
      git.push (ref=f"v{new_ver}")
      console.success ("Pushed to origin")

def _level_from_flags (patch: bool, minor: bool, major: bool) -> str:
   if sum ([ patch, minor, major ]) > 1:
      console.fatal ("--patch, --minor, --major are mutually exclusive")

   if major:
      return "major"
   if minor:
      return "minor"
   if patch:
      return "patch"
   return ""

def release (
   patch: bool = typer.Option (False, "--patch", help="Bump patch version"),
   minor: bool = typer.Option (False, "--minor", help="Bump minor version"),
   major: bool = typer.Option (False, "--major", help="Bump major version"),
   rc: bool = typer.Option (False, "--rc", help="Tag as pre-release candidate"),
   stable: bool = typer.Option (False, "--stable", help="Tag as stable release"),
):
   """Squash, changelog, tag, and push a release.

   Collects commits since the last tag, lets you pick a semver bump,
   generates a changelog entry, squashes unpushed commits into one, tags
   the release, and optionally pushes with a GitHub release. Rolls back
   automatically if anything fails.
   """

   git.require ()

   if rc and stable:
      console.fatal ("--rc and --stable are mutually exclusive")

   level = _level_from_flags (patch, minor, major)

   base = git.base_branch ()
   current = git.branch ()

   if rc:
      return release_rc (level)
   elif not stable and current != base:
      choice = console.choose (
         "Release type",
         [ "rc   (pre-release)", "stable", "quit" ],
      )

      if choice.startswith ("rc"):
         return release_rc (level)
      elif choice == "quit":
         console.muted ("Cancelled")
         raise typer.Exit (0)

   tag, log, count = release_scope ()

   console.header ("Release")

   console.items (f"Commits since {tag or 'beginning'}", log)
   console.out.print ()

   current = current_version ()

   patch_ver, minor_ver, major_ver = _semver_bumps (current)

   if level:
      new_version = version.bump (current, level)
   else:
      console.muted (f"Current: {current}")
      console.out.print ()

      choice = console.choose (
         "Version bump",
         [
            f"patch  {patch_ver}",
            f"minor  {minor_ver}",
            f"major  {major_ver}",
            "custom",
            "quit",
         ],
      )

      if choice.startswith ("patch"):
         new_version = patch_ver
      elif choice.startswith ("minor"):
         new_version = minor_ver
      elif choice.startswith ("major"):
         new_version = major_ver
      elif choice == "custom":
         new_version = console.prompt ("Version:", patch_ver)
      else:
         console.muted ("Cancelled")
         raise typer.Exit (0)

   require_tag_available (new_version)

   subjects = subjects_since (tag, count)
   entry = version.changelog_from_commits (subjects)

   console.label (f"v{new_version}")
   console.divider ()
   console.md (entry)
   console.divider ()
   console.out.print ()

   choice = console.choose (
      f"Release v{new_version}?",
      [ "Yes", "Edit", "No" ],
   )

   if choice == "Edit":
      entry = console.edit (entry)
      console.out.print ()
      console.label (f"v{new_version} (edited)")
      console.divider ()
      console.md (entry)
      console.divider ()
      console.out.print ()
      if not console.confirm (f"Release v{new_version}?"):
         console.muted ("Cancelled")
         raise typer.Exit (0)
   elif choice == "No":
      console.muted ("Cancelled")
      raise typer.Exit (0)

   will_push = console.confirm ("Push after release?")

   if will_push and not git.remote_exists ():
      console.hint ("git remote add origin <url>")
      console.fatal ("No remote configured")

   do_release (new_version, tag, count, will_push)

   console.hint ("make changes, then imp commit")
