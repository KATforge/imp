import typer

from imp import ai, console, git, prompts, version
from imp.commands.release import (
   current_version,
   do_release,
   do_release_rc,
   release_scope,
   require_tag_available,
)
from imp.commands.split import do_split


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

   if level not in ("patch", "minor", "major"):
      console.hint ("use patch, minor, or major")
      console.fatal (f"Invalid level: {level}")

   console.header ("Ship")

   git.stage ()
   files = git.diff_names ()

   if files:
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
   else:
      console.muted ("No staged changes, skipping commit")
      console.out.print ()

   base = git.base_branch ()

   if git.branch () != base:
      do_release_rc (level)
   else:
      tag, _log, count = release_scope ()
      new_version = version.bump (current_version (), level)
      require_tag_available (new_version)
      do_release (new_version, tag, count)
