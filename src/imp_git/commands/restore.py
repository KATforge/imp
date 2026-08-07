from datetime import datetime, timezone
from pathlib import Path

import typer

from imp_git import console, git


def _backup (patch: str, kind: str = "") -> Path:
   root = Path (git.common_dir ())
   folder = root / "imp" / "backups"
   folder.mkdir (parents=True, exist_ok=True)

   stamp = datetime.now (timezone.utc).strftime ("%Y%m%dT%H%M%S%fZ")
   suffix = f"-{kind}" if kind else ""
   path = folder / f"restore-{stamp}{suffix}.patch"
   path.write_text (patch)
   return path


def restore (
   paths: list [str] = typer.Argument (..., help="Paths to restore"),
   staged: bool = typer.Option (False, "--staged", "-S", help="Restore the index"),
   worktree: bool = typer.Option (False, "--worktree", "-W", help="Restore the working tree with --staged"),
   source: str = typer.Option ("", "--source", "-s", help="Restore from this commit"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Restore without confirmation"),
):
   """Preview and restore paths while saving a recoverable patch."""

   git.require ()

   if worktree and not staged:
      console.fatal ("--worktree is only needed together with --staged")
   if source and not git.ref_exists (source):
      console.fatal (f"Cannot resolve source: {source}")

   index_patch = git.diff (staged=True, ref=source, paths=paths) if staged else ""
   worktree_source = source
   if worktree and not worktree_source:
      worktree_source = "HEAD"
   worktree_patch = git.diff (ref=worktree_source, paths=paths) if worktree or not staged else ""
   patch = worktree_patch if worktree or not staged else index_patch

   if not patch and not index_patch:
      console.muted ("No matching changes to restore")
      raise typer.Exit (0)

   console.header ("Restore preview")
   console.out.print (patch.rstrip (), markup=False, highlight=False)

   if not yes and not console.confirm (f"Restore {len (paths)} path(s)?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   backups = []
   if index_patch:
      backups.append ((_backup (index_patch, "index"), True))
   if worktree_patch:
      backups.append ((_backup (worktree_patch, "worktree"), False))
   if not staged:
      backups.append ((_backup (worktree_patch), False))

   git.restore (paths, staged=staged, worktree=worktree, source=source)

   console.success (f"Restored {len (paths)} path(s)")
   for backup, cached in backups:
      flag = "--cached " if cached else ""
      console.hint (f"recover with: imp apply {flag}{backup}")
