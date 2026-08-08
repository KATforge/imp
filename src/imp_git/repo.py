import functools
import json
import os
from pathlib import Path

from imp_git import git

# Per-repo settings live in a committed `.imp` file at the repo root. Same JSON
# format and colon-namespaced grammar as the machine config, so there is one
# mental model. Every key is optional; a project only states what it overrides.
_DEFAULTS = {
   "branch:prefix": "feature/",
   "claim:ttl": "8h",
   "check:commands": [],
   "changelog:skip": [ "chore", "merge", "release" ],
   "commit:max_subject": 72,
   "commit:style": "conventional",
   "done:target": "",
   "done:push": False,
   "done:strategy": "preserve",
   "docs:include": [],
   "docs:mode": "reconcile",
   "docs:path": "",
   "docs:release": False,
   "feature:required": False,
   "ignore:check": True,
   "review:required": False,
   "agent:enforcement": "guarded",
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

def exists () -> bool:
   return path ().is_file ()

def save (cfg: dict):
   p = path ()
   cfg = { key: value for key, value in cfg.items () if key != "schema" }
   temporary = p.with_name (f".{p.name}.{os.getpid ()}.tmp")
   try:
      with temporary.open ("w") as stream:
         stream.write (json.dumps (cfg, indent=3, sort_keys=True) + "\n")
         stream.flush ()
         os.fsync (stream.fileno ())
      temporary.replace (p)
   finally:
      temporary.unlink (missing_ok=True)
   load.cache_clear ()

def changelog_skip () -> list [str]:
   return get ("changelog:skip", _DEFAULTS ["changelog:skip"])

def docs_include () -> list [str]:
   return get ("docs:include", [])

def docs_mode () -> str:
   return get ("docs:mode", "reconcile")

def docs_path () -> str:
   return get ("docs:path", "")

def docs_release () -> bool:
   return bool (get ("docs:release", False))
