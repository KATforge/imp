import re
from pathlib import Path

import typer

from imp import console, git

worktree = typer.Typer (
   name="worktree",
   help="Manage git worktrees for parallel work",
   no_args_is_help=True,
)

_DEFAULT_ROOT = Path.home () / ".worktrees"

def _sanitize (name: str) -> str:
   return re.sub (r"[^A-Za-z0-9._-]+", "-", name).strip ("-")

def _default_path (branch_name: str) -> Path:
   repo = Path (git.common_dir ()).resolve ().parent.name
   return _DEFAULT_ROOT / repo / _sanitize (branch_name)

def _find (name: str) -> dict [str, str] | None:
   target_branch = f"refs/heads/{name}"
   sanitized = _sanitize (name)

   for wt in git.worktrees ():
      if wt.get ("branch") == target_branch:
         return wt

      path = wt.get ("worktree", "")
      if path and Path (path).name == sanitized:
         return wt

   return None

@worktree.command ("add")
def add (
   name: str = typer.Argument (..., help="Branch name for the new worktree"),
   base: str = typer.Option (
      "", "--base", "-b",
      help="Base ref to branch from (default: origin/<trunk>, fetched fresh)",
   ),
   path: str = typer.Option (
      "", "--path", "-p",
      help="Worktree path (default: ~/.worktrees/<repo>/<name>)",
   ),
   no_fetch: bool = typer.Option (
      False, "--no-fetch",
      help="Skip fetching the default base from origin (ignored with --base)",
   ),
):
   """Create a new worktree on a fresh branch, based off the remote trunk.

   By default, the new branch is rooted at the remote trunk (origin/master
   or origin/main, whichever exists), fetched fresh from origin. This
   prevents the surprise of inheriting whatever the host worktree had
   checked out (a feature branch, a release tag, etc.) — historically
   the source of squash-merging unrelated work into trunk.

   Pass --base <ref> to root the new branch at any explicit ref instead
   (a tag, a branch, a SHA). When --base is given, no fetch happens — the
   caller is explicit, so we trust them.
   """

   git.require ()

   wt_path = Path (path) if path else _default_path (name)

   if wt_path.exists ():
      console.fatal (f"Path already exists: {wt_path}")

   if base:
      start_point = base
      base_label = base
   else:
      trunk = git.base_branch ()
      remote_ref = f"origin/{trunk}"

      if git.remote_exists ():
         if not no_fetch:
            console.spin (f"Fetching origin/{trunk}...", git.fetch, remote="origin", refspec=trunk)

         if not git.ref_exists (remote_ref):
            console.hint (f"git fetch origin {trunk}")
            console.fatal (f"No {remote_ref} ref; cannot determine safe base")

         start_point = remote_ref
         base_label = remote_ref
      else:
         if not git.ref_exists (trunk):
            console.hint (f"create '{trunk}' or pass --base <ref>")
            console.fatal (f"No remote and no local '{trunk}'; cannot determine safe base")

         start_point = trunk
         base_label = f"{trunk} (no remote)"

   wt_path.parent.mkdir (parents=True, exist_ok=True)

   console.header ("Worktree")
   console.label ("Branch")
   console.item (name)
   console.label ("Base")
   console.item (base_label)
   console.label ("Path")
   console.item (str (wt_path))

   git.worktree_add (str (wt_path), name, start_point)

   console.success (f"Worktree ready at {wt_path}")
   console.hint (f"cd {wt_path}")

@worktree.command ("list")
def list_ ():
   """List all worktrees for this repo."""

   git.require ()

   entries = git.worktrees ()
   if not entries:
      console.muted ("No worktrees")
      raise typer.Exit (0)

   console.header ("Worktrees")
   for wt in entries:
      branch = wt.get ("branch", "").removeprefix ("refs/heads/") or "(detached)"
      path = wt.get ("worktree", "")
      console.label (branch)
      console.item (path)

@worktree.command ("path")
def path (
   name: str = typer.Argument (..., help="Worktree or branch name"),
):
   """Print the filesystem path of a worktree (for shell eval)."""

   git.require ()

   wt = _find (name)
   if not wt:
      console.fatal (f"No worktree for {name}")

   console.out.print (wt ["worktree"])

@worktree.command ("remove")
def remove (
   name: str = typer.Argument (..., help="Worktree or branch name"),
   force: bool = typer.Option (False, "--force", "-f", help="Remove even with uncommitted changes"),
   delete_branch: bool = typer.Option (False, "--delete-branch", "-d", help="Also delete the branch"),
):
   """Remove a worktree (and optionally delete its branch)."""

   git.require ()

   wt = _find (name)
   if not wt:
      console.fatal (f"No worktree for {name}")

   wt_path = wt ["worktree"]
   branch_ref = wt.get ("branch", "").removeprefix ("refs/heads/")

   git.worktree_remove (wt_path, force=force)
   console.success (f"Removed {wt_path}")

   if delete_branch and branch_ref:
      git.delete_branch (branch_ref, force=force)
      console.success (f"Deleted branch {branch_ref}")

@worktree.command ("prune")
def prune ():
   """Clean up stale worktree entries (worktrees whose directories were deleted)."""

   git.require ()
   git.worktree_prune ()
   console.success ("Pruned stale worktree entries")
