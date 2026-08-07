import hashlib
import json
from pathlib import Path

from imp_git import git


def repository () -> str:
   """Fingerprint the exact branch, index, worktree, and untracked state."""

   root = Path (git.repo_root ())
   untracked = []
   for relative in git.untracked_files ():
      path = root / relative
      try:
         digest = hashlib.sha256 (path.read_bytes ()).hexdigest ()
      except OSError:
         digest = "missing"
      untracked.append ({ "path": relative, "sha256": digest })

   value = {
      "branch": git.branch (),
      "head": git.rev_parse ("HEAD"),
      "staged": git.capture ("diff", "--cached", "--binary", "--no-ext-diff", "--no-renames"),
      "unstaged": git.capture ("diff", "--binary", "--no-ext-diff", "--no-renames"),
      "untracked": untracked,
   }
   payload = json.dumps (value, sort_keys=True, separators=(",", ":")).encode ()
   return f"sha256:{hashlib.sha256 (payload).hexdigest ()}"


def values (value: dict) -> str:
   """Fingerprint an explicit deterministic value."""

   payload = json.dumps (value, sort_keys=True, separators=(",", ":")).encode ()
   return f"sha256:{hashlib.sha256 (payload).hexdigest ()}"
