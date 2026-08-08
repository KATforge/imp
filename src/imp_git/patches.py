from pathlib import Path
from typing import Any

from imp_git import git, state


def _temporary_index () -> Path:
   return state.temporary ("patch-index-")


def desired_index (paths: list [str], mode: str) -> Path:
   """Build an isolated index containing the selected final content."""

   index = _temporary_index ()
   if git.ref_exists ("HEAD"):
      git.index_read_tree (index, "HEAD")
   else:
      git.index_read_empty (index)
   if mode == "all":
      git.index_add_worktree (index, paths)
      return index

   for path in paths:
      git.index_set (index, path, git.index_entry (path))

   return index


def _parts (path: str, patch: str) -> list [dict [str, str]]:
   lines = patch.splitlines (keepends=True)
   starts = [index for index, line in enumerate (lines) if line.startswith ("@@ ")]
   metadata = any (
      line.startswith (("old mode ", "new mode ", "new file mode ", "deleted file mode ", "GIT binary patch"))
      for line in lines
   )
   if len (starts) <= 1 or metadata:
      return [ { "id": f"{path}#1", "path": path, "patch": patch } ]

   header = [line for line in lines [:starts [0]] if not line.startswith ("index ")]
   values = []
   for number, start in enumerate (starts, start=1):
      end = starts [number] if number < len (starts) else len (lines)
      values.append ({
         "id": f"{path}#{number}",
         "path": path,
         "patch": "".join ([ *header, *lines [start:end] ]),
      })

   return values


def changes (paths: list [str], mode: str) -> tuple [list [dict [str, str]], str]:
   """Return every selected change section and the exact desired tree."""

   index = desired_index (paths, mode)
   try:
      values = []
      for path in paths:
         patch = git.index_diff (index, path)
         if not patch:
            raise state.StateError (f"Selected path has no committable change: {path}")
         values.extend (_parts (path, patch))

      return values, git.index_write_tree (index)
   finally:
      index.unlink (missing_ok=True)


def content (changes: list [dict [str, str]]) -> str:
   """Render change identities and patches for the commit planner."""

   return "\n".join (
      f"--- {change ['id']} ---\n{change ['patch']}"
      for change in changes
   )


def apply (index: Path, changes: list [dict [str, Any]], change_ids: list [str]):
   """Apply selected planned changes to one isolated index."""

   by_id = { str (change ["id"]): str (change ["patch"]) for change in changes }
   for change_id in change_ids:
      patch = by_id.get (change_id)
      if patch is None:
         raise state.StateError (f"Unknown planned change: {change_id}")
      git.index_apply (index, patch)
