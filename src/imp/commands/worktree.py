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
   base: str = typer.Option ("", "--base", "-b", help="Base branch (default: current HEAD)"),
   path: str = typer.Option ("", "--path", "-p", help="Worktree path (default: ~/.worktrees/<repo>/<name>)"),
):
   """Create a new worktree on a fresh branch."""

   git.require ()

   wt_path = Path (path) if path else _default_path (name)

   if wt_path.exists ():
      console.fatal (f"Path already exists: {wt_path}")

   wt_path.parent.mkdir (parents=True, exist_ok=True)

   console.header ("Worktree")
   console.label ("Branch")
   console.item (name)
   console.label ("Path")
   console.item (str (wt_path))

   git.worktree_add (str (wt_path), name, base)

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
