import functools
import json
from pathlib import Path

from imp_git import git

# Per-repo settings live in a committed `.imp` file at the repo root. Same JSON
# format and colon-namespaced grammar as the machine config, so there is one
# mental model. Every key is optional; a project only states what it overrides.
_DEFAULTS = {
   "branch:prefix": "feature/",
   "claim:ttl": "8h",
   "check:commands": [],
   "commit:max_subject": 72,
   "commit:style": "conventional",
   "done:target": "",
   "done:push": False,
   "done:strategy": "preserve",
   "feature:required": False,
   "ignore:check": True,
   "review:required": False,
   "worktree:root": "",
   "worktree:setup": [],
   "worktree:share": [],
}

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
   if default is None:
      default = _DEFAULTS.get (key)

   return load ().get (key, default)
