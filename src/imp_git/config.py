import functools
import json
import os
from pathlib import Path

_DEFAULTS = {
   "schema": "imp.machine.v1",
   "provider": "claude",
   "model:fast": "haiku",
   "model:smart": "sonnet",
}


def path () -> Path:
   xdg = os.environ.get ("XDG_CONFIG_HOME", "") or str (Path.home () / ".config")

   return Path (xdg) / "imp" / "config.json"

@functools.cache
def load () -> dict:
   """Return defaults plus an explicit machine configuration file."""

   cfg = dict (_DEFAULTS)

   p = path ()
   if p.is_file ():
      try:
         stored = json.loads (p.read_text ())
         cfg.update (stored)
      except json.JSONDecodeError:
         from imp_git import console
         console.warn ("Invalid config file, using defaults")
      except OSError:
         pass
   return cfg


def save (cfg: dict):
   p = path ()
   p.parent.mkdir (parents=True, exist_ok=True)
   cfg = { **cfg, "schema": "imp.machine.v1" }
   p.write_text (json.dumps (cfg, indent=3, sort_keys=True) + "\n")
   load.cache_clear ()

def get (key: str) -> str:
   return load ().get (key, _DEFAULTS.get (key, ""))
