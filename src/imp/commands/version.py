from pathlib import Path

import typer

from imp import console, git
from imp import version as version_mod


def version (
   sync: bool = typer.Option (False, "--sync", help="Write the tag version into every drifted manifest"),
):
   """Show manifest versions against the canonical git tag.

   The highest semver tag is the canonical version; package.json,
   composer.json, and pyproject.toml carry downstream copies. Lists each
   manifest with its declared version and flags drift. With --sync the
   drifted manifests are rewritten to match the tag; the changes are left
   uncommitted (land them with imp commit or the next release).

   Exits 1 when drift exists and --sync was not given, so it can gate CI.
   """

   git.require ()

   tag = git.highest_tag ()
   if not tag:
      console.fatal ("No semver tags — nothing to sync against")

   ver = tag.lstrip ("v")
   root = Path (git.repo_root ())

   console.header ("Version")
   console.label (tag)

   drifted = False

   for path in version_mod.manifest_paths (root):
      declared = version_mod.read_manifest_version (path)
      if declared is None:
         continue

      rel = path.relative_to (root)

      if declared == ver:
         console.success (f"{rel}  {declared}")
      else:
         drifted = True
         console.warn (f"{rel}  {declared}  (tag says {ver})")

   if not drifted:
      return

   if not sync:
      console.hint ("imp version --sync")
      raise typer.Exit (1)

   for p in version_mod.sync_manifests (root, ver):
      console.success (f"Synced {p.relative_to (root)} → {ver}")

   console.hint ("commit with: imp commit")
