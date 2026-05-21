import typer

from imp import console, git, version
from imp.commands.release import (
   current_version,
   do_release,
   release_scope,
   require_tag_available,
)

def tag (
   patch: bool = typer.Option (False, "--patch", help="Bump patch (default chooser if no flag)"),
   minor: bool = typer.Option (False, "--minor", help="Bump minor"),
   major: bool = typer.Option (False, "--major", help="Bump major"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Skip confirmation"),
   no_push: bool = typer.Option (False, "--no-push", help="Update, commit, and tag but don't push"),
):
   """Bump the highest semver tag, update CHANGELOG.md, commit, and push.

   Picks the next version from the highest existing v-prefixed tag,
   writes a CHANGELOG.md entry from commits since the last tag, commits it
   as chore: release vX.Y.Z, tags HEAD, and pushes. No squash.
   """

   git.require ()
   git.require_clean ("imp commit first")

   levels = { "patch": patch, "minor": minor, "major": major }
   selected = [ k for k, v in levels.items () if v ]

   if len (selected) > 1:
      console.fatal ("Pick one of --patch/--minor/--major")

   current = current_version ()

   if selected:
      level = selected [0]
   else:
      level = console.choose (
         f"Bump from v{current}?",
         [ "patch", "minor", "major" ],
      ).lower ()

   new_version = version.bump (current, level)
   if new_version == level:
      console.fatal (f"Cannot parse current version: {current}")

   require_tag_available (new_version)

   last_tag, log, count = release_scope ()

   console.header ("Tag")
   console.items (f"Commits since {last_tag or 'beginning'}", log)
   console.out.print ()
   console.label (f"v{current} → v{new_version}")
   console.out.print ()

   if not yes and not console.confirm (f"Tag v{new_version}?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   will_push = not no_push and git.remote_exists ()

   if no_push:
      console.muted ("--no-push: keeping changes local")
   elif not git.remote_exists ():
      console.muted ("No remote configured, skipping push")

   do_release (new_version, last_tag, count, will_push=will_push, squash=False)
