import os
import subprocess
from pathlib import Path

from imp_git import ai, console, git, prompts, state

OURS = "ours"
THEIRS = "theirs"
EDIT = "edit"
RESOLVE = "resolve"

_CHOICES = {
   f"{OURS}      keep trunk": OURS,
   f"{THEIRS}    take the feature": THEIRS,
   f"{EDIT}      open $EDITOR on the merged file": EDIT,
   f"{RESOLVE}   let the model resolve it": RESOLVE,
}


def _editor () -> list [str]:
   value = os.environ.get ("IMP_EDITOR", "") or os.environ.get ("VISUAL", "") or os.environ.get ("EDITOR", "")
   if not value:
      raise state.StateError ("Set $EDITOR to resolve a conflict by hand")

   return value.split ()


def _conflicted (path: str) -> list [str]:
   output = git.run_at (path, "diff", "--name-only", "--diff-filter=U", check=False)

   return [ line.strip () for line in output.stdout.splitlines () if line.strip () ]


def _preview (path: str, name: str) -> str:
   body = Path (path, name).read_text (errors="replace").splitlines ()
   marked = [ index for index, line in enumerate (body) if line.startswith ("<<<<<<<") ]
   if not marked:
      return ""
   start = max (0, marked [0] - 2)

   return "\n".join (body [start:marked [0] + 14])


def _resolve_with_model (path: str, name: str):
   body = Path (path, name).read_text (errors="replace")
   merged = ai.strip_fences (ai.smart (prompts.resolve_conflict (name, ai.truncate (body)))).strip ()
   if not merged or "<<<<<<<" in merged:
      raise state.StateError (f"The model could not resolve {name}")
   Path (path, name).write_text (merged if merged.endswith ("\n") else merged + "\n")


def _apply_choice (path: str, name: str, choice: str):
   if choice in { OURS, THEIRS }:
      git.run_at (path, "checkout", f"--{choice}", "--", name)
   elif choice == EDIT:
      subprocess.run ([ *_editor (), name ], cwd=path, check=False)
      if "<<<<<<<" in Path (path, name).read_text (errors="replace"):
         raise state.StateError (f"Conflict markers remain in {name}")
   else:
      _resolve_with_model (path, name)
   git.run_at (path, "add", "--", name)


def resolve (
   worktree: str,
   target_oid: str,
   feature_oid: str,
   *,
   choice: str = "",
) -> tuple [str, list [dict [str, str]]]:
   """Merge in a scratch worktree, resolve every conflict, and return the resolved tree."""

   git.run_at (worktree, "checkout", "--detach", target_oid)
   merge = git.run_at (worktree, "merge", "--no-commit", "--no-ff", feature_oid, check=False)
   if merge.returncode == 0:
      return git.run_at (worktree, "write-tree").stdout.strip (), []

   decisions = []
   for name in _conflicted (worktree):
      selected = choice
      if not selected:
         console.header (f"Integration conflict · {name}")
         body = _preview (worktree, name)
         if body:
            console.items ("Hunk", body)
         selected = _CHOICES [console.choose ("Resolve with", list (_CHOICES))]
      _apply_choice (worktree, name, selected)
      decisions.append ({ "choice": selected, "path": name })

   remaining = _conflicted (worktree)
   if remaining:
      raise state.StateError (f"Unresolved conflict: {', '.join (remaining)}")

   return git.run_at (worktree, "write-tree").stdout.strip (), decisions
