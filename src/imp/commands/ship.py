from datetime import date
from pathlib import Path

import typer

from imp import ai, console, git, prompts, version
from imp.commands.release import _push_release, _squash_commits, _write_changelog


def ship (
   level: str = typer.Argument ("patch", help="Version bump: patch, minor, or major"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Commit all changes and release in one shot.

   Stages everything, generates a commit message, bumps the version,
   updates the changelog, squashes, tags, and pushes. No prompts.
   Equivalent to imp commit -a followed by imp release with auto-accept.
   """

   git.require ()

   if level not in ("patch", "minor", "major"):
      console.err (f"Invalid level: {level}")
      console.hint ("use patch, minor, or major")
      raise typer.Exit (1)

   console.header ("Ship")

   git.stage (all=True)
   d = git.diff (staged=True)

   if not d:
      console.muted ("No changes to ship")
      raise typer.Exit (0)

   b = git.branch ()
   msg = ai.commit_message (prompts.commit (d, b, whisper))

   console.label ("Commit")
   console.item (msg)
   git.commit (msg)
   console.success ("Committed")
   console.out.print ()

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

   highest = git.highest_tag ()
   current = highest.lstrip ("v") if highest else "0.0.0"
   if not current:
      current = "0.0.0"

   new_version = version.bump (current, level)

   if git.tag_exists (f"v{new_version}"):
      console.err (f"Tag v{new_version} already exists")
      console.hint (f"pick a different version, or: git tag -d v{new_version}")
      raise typer.Exit (1)

   if tag:
      subjects = git.log_subjects (rev_range=f"{tag}..HEAD")
   else:
      subjects = git.log_subjects (count=count)

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

   if git.remote_exists ():
      try:
         _push_release (new_version, entry, can_squash)
      except Exception as e:
         console.err (f"Push failed: {e}")
         raise typer.Exit (1) from None
   else:
      console.muted ("No remote, skipped push")
