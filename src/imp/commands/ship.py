import shutil
import subprocess
from datetime import date
from pathlib import Path

import typer

from imp import ai, console, git, prompts, version
from imp.commands.release import current_version
from imp.commands.split import do_split


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


def _push_release (ver: str, entry: str):
   if git.has_upstream ():
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


def ship (
   level: str = typer.Argument ("patch", help="Version bump: patch, minor, or major"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Split changes into logical commits, then release.

   Stages everything, uses AI to split into logical commits (or a single
   commit if only one file changed), then bumps the version, updates the
   changelog, tags, and pushes. Preserves feature commit history.
   """

   git.require ()

   base = git.base_branch ()
   if git.branch () != base:
      console.warn (f"Releasing from {git.branch ()}, not {base}")

   if level not in ("patch", "minor", "major"):
      console.hint ("use patch, minor, or major")
      console.fatal (f"Invalid level: {level}")

   console.header ("Ship")

   git.stage (all=True)
   files = git.diff_names ()

   if not files:
      console.muted ("No changes to ship")
      raise typer.Exit (0)

   did_split = False

   if len (files) >= 2:
      did_split = do_split (files, whisper, yes=True) is not None

   if not did_split:
      d = git.diff (staged=True)
      b = git.branch ()
      msg = ai.commit_message (prompts.commit (d, b, whisper))
      console.item (msg)
      git.commit (msg)
      console.success ("Committed")

   console.out.print ()

   tag = git.last_tag ()
   if tag:
      subjects = git.log_subjects (rev_range=f"{tag}..HEAD")
   else:
      subjects = git.log_subjects (count=20)

   new_version = version.bump (current_version (), level)

   if git.tag_exists (f"v{new_version}"):
      console.hint (f"pick a different version, or: git tag -d v{new_version}")
      console.fatal (f"Tag v{new_version} already exists")

   entry = version.changelog_from_commits (subjects)
   today = date.today ().isoformat ()
   new_entry = f"## [{new_version}] - {today}\n\n{entry}"

   root = git.repo_root ()
   changelog_path = Path (root) / "CHANGELOG.md"

   original_head = git.rev_parse ("HEAD")
   original_changelog = ""
   if changelog_path.is_file ():
      original_changelog = changelog_path.read_text ()

   try:
      _write_changelog (changelog_path, new_entry)
      console.success ("Updated CHANGELOG.md")

      git.add ([ str (changelog_path) ])
      git.commit (f"chore: release v{new_version}")
      console.success (f"Release commit: v{new_version}")

      git.tag (f"v{new_version}")
      console.success (f"Tagged v{new_version}")

   except (subprocess.CalledProcessError, OSError) as e:
      msg = getattr (e, "stderr", "") or str (e)
      console.err (f"Release failed: {msg.strip ()}")
      console.warn ("Rolling back release...")
      git.tag_delete (f"v{new_version}")
      git.reset (original_head, hard=True)
      if original_changelog:
         changelog_path.write_text (original_changelog)
      elif changelog_path.is_file ():
         changelog_path.unlink ()
      raise typer.Exit (1) from None

   will_push = git.remote_exists ()

   if will_push:
      try:
         _push_release (new_version, entry)
      except (subprocess.CalledProcessError, OSError) as e:
         msg = getattr (e, "stderr", "") or str (e)
         console.err (f"Push failed: {msg.strip ()}")
         raise typer.Exit (1) from None
   else:
      console.muted ("No remote, skipped push")
