import json
import os
from pathlib import Path

_DEFAULTS = {
   "provider": "claude",
   "model:fast": "haiku",
   "model:smart": "sonnet",
}

_ENV_OVERRIDES = {
   "provider": "IMP_AI_PROVIDER",
   "model:fast": "IMP_AI_MODEL_FAST",
   "model:smart": "IMP_AI_MODEL_SMART",
}


def path () -> Path:
   xdg = os.environ.get ("XDG_CONFIG_HOME", "")
   if not xdg:
      xdg = str (Path.home () / ".config")
   return Path (xdg) / "imp" / "config.json"


def load () -> dict:
   cfg = dict (_DEFAULTS)

   p = path ()
   if p.is_file ():
      try:
         stored = json.loads (p.read_text ())
         cfg.update (stored)
      except (json.JSONDecodeError, OSError):
         pass

   for key, env in _ENV_OVERRIDES.items ():
      val = os.environ.get (env, "")
      if val:
         cfg [key] = val

   return cfg


def save (cfg: dict):
   p = path ()
   p.parent.mkdir (parents=True, exist_ok=True)
   p.write_text (json.dumps (cfg, indent=3) + "\n")


def get (key: str) -> str:
   return load ().get (key, _DEFAULTS.get (key, ""))
