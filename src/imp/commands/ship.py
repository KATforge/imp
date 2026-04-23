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

def _resolve_level (patch: bool, minor: bool, major: bool) -> str:
   if sum ([ patch, minor, major ]) > 1:
      console.fatal ("--patch, --minor, --major are mutually exclusive")

   if major:
      return "major"
   if minor:
      return "minor"
   return "patch"

def ship (
   patch: bool = typer.Option (False, "--patch", help="Bump patch version (default)"),
   minor: bool = typer.Option (False, "--minor", help="Bump minor version"),
   major: bool = typer.Option (False, "--major", help="Bump major version"),
   rc: bool = typer.Option (False, "--rc", help="Tag as pre-release candidate"),
   stable: bool = typer.Option (False, "--stable", help="Tag as stable release"),
   squash: bool = typer.Option (False, "--squash", help="Squash split commits into a single release commit"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
):
   """Split changes into logical commits, then release.

   Stages everything, uses AI to split into logical commits (or a single
   commit if only one file changed), then bumps the version, updates the
   changelog, tags, and pushes. Preserves feature commit history.
   """

   git.require ()

   if rc and stable:
      console.fatal ("--rc and --stable are mutually exclusive")

   level = _resolve_level (patch, minor, major)

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

   if rc:
      is_rc = True
   elif stable:
      is_rc = False
   else:
      is_rc = git.branch () != base and console.choose (
         "Release type",
         [ "rc   (pre-release)", "stable" ],
      ).startswith ("rc")

   if is_rc:
      do_release_rc (level)
   else:
      tag, _log, count = release_scope ()
      new_version = version.bump (current_version (), level)
      require_tag_available (new_version)
      do_release (new_version, tag, count, squash=squash)
