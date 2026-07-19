import functools
import json
from pathlib import Path

from imp import git

# Per-repo settings live in a committed `.imp` file at the repo root. Same JSON
# format and colon-namespaced grammar as the machine config, so there is one
# mental model. Every key is optional; a project only states what it overrides.
_DEFAULTS = {
   "changelog:skip": [ "chore", "merge", "release" ],
   "docs:include": [],
   "docs:mode": "reconcile",
   "docs:path": "",
   "docs:release": False,
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
      from imp import console
      console.warn ("Invalid .imp file, ignoring")
      return {}

   return data if isinstance (data, dict) else {}

def get (key: str, default=None):
   if default is None:
      default = _DEFAULTS.get (key)

   return load ().get (key, default)

def exists () -> bool:
   return path ().is_file ()

def save (cfg: dict):
   p = path ()
   p.write_text (json.dumps (cfg, indent=3, sort_keys=True) + "\n")
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
