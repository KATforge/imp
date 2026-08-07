#!/usr/bin/env python3
import json
import shlex
import shutil
from pathlib import Path
from typing import Any

SOURCE = Path (__file__).resolve ().parent
INSTALL = Path.home () / ".config" / "katforge" / "agents"


def _read (path: Path) -> dict [str, Any]:
   if not path.is_file ():
      return {}
   value = json.loads (path.read_text ())
   if not isinstance (value, dict):
      raise ValueError (f"Expected an object: {path}")
   return value


def _write (path: Path, value: dict [str, Any]):
   path.parent.mkdir (parents=True, exist_ok=True)
   temporary = path.with_suffix (f"{path.suffix}.tmp")
   temporary.write_text (json.dumps (value, indent=2, sort_keys=False) + "\n")
   temporary.replace (path)


def _hooks (provider: str) -> dict [str, Any]:
   value = _read (SOURCE / "hooks.json")
   guard = shlex.quote (str (INSTALL / "agent_guard.py"))
   encoded = json.dumps (value).replace ("KATFORGE_AGENT_GUARD", guard).replace ("PROVIDER", provider)
   return json.loads (encoded)


def _merge (path: Path, provider: str):
   current = _read (path)
   incoming = _hooks (provider) ["hooks"]
   configured = current.setdefault ("hooks", {})
   for event, groups in incoming.items ():
      existing = configured.setdefault (event, [])
      existing [:] = [
         group for group in existing
         if "katforge/agents/agent_guard.py" not in json.dumps (group)
      ]
      existing.extend (groups)
   _write (path, current)


def main ():
   INSTALL.mkdir (parents=True, exist_ok=True)
   shutil.copy2 (SOURCE / "agent_guard.py", INSTALL / "agent_guard.py")
   shutil.copy2 (SOURCE / "adapter.json", INSTALL / "adapter.json")
   skill = SOURCE / "skills" / "katforge-development"
   for root in [ Path.home () / ".codex" / "skills", Path.home () / ".claude" / "skills" ]:
      target = root / skill.name
      if target.exists ():
         shutil.rmtree (target)
      target.parent.mkdir (parents=True, exist_ok=True)
      shutil.copytree (skill, target)
   _merge (Path.home () / ".codex" / "hooks.json", "codex")
   _merge (Path.home () / ".claude" / "settings.json", "claude")
   print (f"Installed KATforge agent adapters in {INSTALL}")
   print ("Codex: run /hooks once and trust the KATforge hooks")


if __name__ == "__main__":
   main ()
