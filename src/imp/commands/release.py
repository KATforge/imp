import shutil
import subprocess
from datetime import date
from pathlib import Path

import typer

from imp import console, git, version


def _write_changelog (path: Path, new_entry: str):
   if path.is_file ():
      content = path.read_text ()

      lines = content.splitlines (keepends=True)
      insert_at = None
      for i, line in enumerate (lines):
         if line.lstrip ().startswith ("## "):
            insert_at = i
            break

      if insert_at is not None:
         before = "".join (lines [:insert_at])
         after = "".join (lines [insert_at:])
         content = before + new_entry + "\n\n" + after
      else:
         content = content + "\n" + new_entry + "\n"

      path.write_text (content)
   else:
      path.write_text (
         f"# Changelog\n\n"
         f"All notable changes to this project will be documented in this file.\n\n"
         f"{new_entry}\n"
      )


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
      git.stage (all=True)
      git.commit (summary)
      console.success (f"Squashed {count} commits")
   else:
      git.add ([ str (changelog_path) ])
      git.commit (summary)
      if tag:
         console.muted ("Commits already pushed, skipped squash")

   return can_squash


def _push_release (ver: str, entry: str, can_squash: bool):
   if git.has_upstream ():
      if can_squash:
         git.push (force_lease=True)
      else:
         git.push ()
   else:
      b = git.branch ()
      git.push (set_upstream=True, target=b)

   git.push (ref=f"v{ver}")
   console.success ("Pushed to origin")

   if shutil.which ("gh"):
      try:
         subprocess.run (
            [
               "gh", "release", "create",
               f"v{ver}",
               "--title", f"v{ver}",
               "--notes", entry,
            ],
            capture_output=True,
            text=True,
            check=True,
         )
         console.success ("Created GitHub release")
      except subprocess.CalledProcessError:
         console.muted ("GitHub release skipped (gh auth or repo issue)")


def release ():
   """Squash, changelog, tag, and push a release.

   Collects commits since the last tag, lets you pick a semver bump,
   generates a changelog entry, squashes unpushed commits into one, tags
   the release, and optionally pushes with a GitHub release. Rolls back
   automatically if anything fails.
   """

   git.require ()
   git.require_clean ("imp commit first")

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

   count = len (log.splitlines ())

   console.header ("Release")

   console.items (f"Commits since {tag or 'beginning'}", log)

   highest = git.highest_tag ()
   current = highest.lstrip ("v") if highest else "0.0.0"
   if not current:
      current = "0.0.0"

   patch_ver = version.bump (current, "patch")
   minor_ver = version.bump (current, "minor")
   major_ver = version.bump (current, "major")

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

   if git.tag_exists (f"v{new_version}"):
      console.err (f"Tag v{new_version} already exists")
      console.hint (f"pick a different version, or: git tag -d v{new_version}")
      raise typer.Exit (1)

   if tag:
      subjects = git.log_subjects (rev_range=f"{tag}..HEAD")
   else:
      subjects = git.log_subjects (count=count)

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
      console.err ("No remote configured")
      console.hint ("git remote add origin <url>")
      raise typer.Exit (1)

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

   def rollback ():
      nonlocal committed
      console.warn ("Rolling back...")
      git.tag_delete (f"v{new_version}")
      if committed:
         git.reset (original_head, hard=True)
      if original_changelog:
         changelog_path.write_text (original_changelog)
      elif changelog_path.is_file ():
         changelog_path.unlink ()
      console.err ("Release failed")

   try:
      _write_changelog (changelog_path, new_entry)
      console.success ("Updated CHANGELOG.md")

      can_squash = _squash_commits (tag, summary, changelog_path, count)
      committed = True

      git.tag (f"v{new_version}")
      console.success (f"Tagged v{new_version}")

   except Exception as e:
      console.err (f"Release failed: {e}")
      rollback ()
      raise typer.Exit (1) from None

   if will_push:
      try:
         _push_release (new_version, entry, can_squash)
      except Exception as e:
         console.err (f"Push failed: {e}")
         raise typer.Exit (1) from None

   console.hint ("make changes, then imp commit")
