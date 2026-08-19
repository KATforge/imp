import functools
import json
from pathlib import Path

from imp_git import git


def path () -> Path:
   root = git.repo_root ()
   base = Path (root) if root else Path.cwd ()

   return base / ".imp"

@functools.cache
def load () -> dict:
   p = path ()
   if not p.is_file ():
      return {}

   try:
      data = json.loads (p.read_text ())
   except (json.JSONDecodeError, OSError):
      from imp_git import console
      console.warn ("Invalid .imp file, ignoring")
      return {}

   if not isinstance (data, dict):
      return {}
   schema = data.pop ("schema", None)
   if schema not in { None, "imp.config.v1" }:
      from imp_git import state
      raise state.StateError (f"Unsupported repository configuration {schema}; update Imp")
   return data

def get (key: str, default=None):
   return load ().get (key, default)
