import json
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Annotated

import typer

from imp_git import ai, config, console, git, identity, repo, result, runtime

_CODEX_EVENTS = { "preToolUse" }
_CLAUDE_EVENTS = [ "PreToolUse" ]


def _check (name: str, cmd: str, url: str, required: bool = True) -> bool:
   path = shutil.which (cmd)
   if path:
      try:
         result = subprocess.run (
            [ cmd, "--version" ],
            capture_output=True,
            text=True,
            timeout=5,
         )
         version = result.stdout.strip ().splitlines () [0] if result.stdout.strip () else "installed"
      except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
         version = "installed"
      console.success (f"{name} ({version})")
      return True

   if required:
      console.err (f"{name} not found")
      console.item (url)
      return False

   console.muted (f"  {name} not found (optional)")
   console.item (url)
   return True


def _codex_hooks (cwd: Path) -> list [dict]:
   """Ask Codex for its effective hook inventory, including trust state."""

   process = subprocess.Popen (
      [ "codex", "app-server", "--stdio" ],
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.DEVNULL,
      text=True,
   )
   if not process.stdin or not process.stdout:
      process.kill ()
      return []

   lines: queue.Queue [str] = queue.Queue ()

   def read ():
      for line in process.stdout:
         lines.put (line)

   threading.Thread (target=read, daemon=True).start ()

   def send (value: dict):
      process.stdin.write (json.dumps (value) + "\n")
      process.stdin.flush ()

   def receive (request_id: int) -> dict:
      while True:
         message = json.loads (lines.get (timeout=5))
         if message.get ("id") == request_id:
            return message

   try:
      send ({
         "id": 0,
         "method": "initialize",
         "params": {
            "clientInfo": {
               "name": "imp",
               "title": "Imp",
               "version": "2",
            },
         },
      })
      receive (0)
      send ({ "method": "initialized" })
      send ({ "id": 1, "method": "hooks/list", "params": { "cwds": [ str (cwd) ] } })
      response = receive (1)
   except (json.JSONDecodeError, OSError, queue.Empty, subprocess.SubprocessError):
      return []
   finally:
      process.terminate ()
      try:
         process.wait (timeout=2)
      except subprocess.TimeoutExpired:
         process.kill ()

   data = response.get ("result", {}).get ("data", [])
   if not data:
      return []

   return [
      hook for hook in data [0].get ("hooks", [])
      if "imp/agents/agent_guard.py" in str (hook.get ("command", ""))
   ]


def _codex_guard (cwd: Path) -> tuple [bool, str]:
   hooks = _codex_hooks (cwd)
   events = { str (hook.get ("eventName")) for hook in hooks }
   trusted = all (hook.get ("trustStatus") in { "managed", "trusted" } for hook in hooks)
   enabled = all (hook.get ("enabled") is True for hook in hooks)
   active = events == _CODEX_EVENTS and trusted and enabled
   if active:
      return True, "trusted"
   if hooks and any (hook.get ("trustStatus") in { "modified", "untrusted" } for hook in hooks):
      return False, "review-required"
   if hooks:
      return False, "disabled"

   return False, "unavailable"


def _claude_events (settings: Path) -> dict [str, bool]:
   """Report guard registration per hook event from parsed Claude settings."""

   try:
      value = json.loads (settings.read_text ())
   except (FileNotFoundError, json.JSONDecodeError, OSError):
      value = {}
   hooks = value.get ("hooks", {}) if isinstance (value, dict) else {}
   events = {}
   for event in _CLAUDE_EVENTS:
      groups = hooks.get (event, []) if isinstance (hooks, dict) else []
      events [event] = any (
         "imp/agents/agent_guard.py" in str (entry.get ("command", ""))
         for group in groups if isinstance (group, dict)
         for entry in group.get ("hooks", []) if isinstance (entry, dict)
      ) if isinstance (groups, list) else False
   return events


def _guard_drift (install: Path) -> str:
   """Compare the deployed guard against the packaged adapter source."""

   deployed = install / "agent_guard.py"
   packaged = Path (__file__).resolve ().parents [3] / "adapters" / "agent_guard.py"
   if not deployed.is_file () or not packaged.is_file ():
      return "unknown"
   return "in-sync" if deployed.read_bytes () == packaged.read_bytes () else "modified"


def _agent_report () -> dict:
   install = Path.home () / ".config" / "imp" / "agents"
   metadata_path = install / "adapter.json"
   try:
      metadata = json.loads (metadata_path.read_text ())
   except (FileNotFoundError, json.JSONDecodeError, OSError):
      metadata = {}
   installed = bool (metadata.get ("version")) and (install / "agent_guard.py").is_file ()
   providers = []
   for name, settings, skill in [
      ("claude", Path.home () / ".claude" / "settings.json", Path.home () / ".claude" / "skills"),
      ("codex", Path.home () / ".codex" / "hooks.json", Path.home () / ".codex" / "skills"),
   ]:
      if name == "claude":
         events = _claude_events (settings)
         hook = all (events.values ())
      else:
         try:
            text = settings.read_text ()
         except OSError:
            text = ""
         hook = "imp/agents/agent_guard.py" in text
         events = {}
      workflow = (skill / "imp-development" / "SKILL.md").is_file ()
      guards = hook and installed
      trust = "not-required"
      if name == "codex" and guards:
         guards, trust = _codex_guard (Path.cwd ())
      providers.append ({
         "actor": identity.resource ("actor", name, "session"),
         "automatic_bootstrap": guards,
         "context_injection": guards,
         "effective_enforcement": "guarded" if guards else "guided" if workflow else "none",
         "events": events,
         "guards": guards,
         "hook_mechanism": True,
         "hook_trust": trust,
         "hooks": hook,
         "installed": installed,
         "provider": name,
         "sandbox": False,
         "skill": workflow,
         "version": metadata.get ("version"),
      })
   providers.append ({
      "actor": identity.resource ("actor", "gemini", "session"),
      "automatic_bootstrap": False,
      "context_injection": False,
      "effective_enforcement": "none",
      "events": {},
      "guards": False,
      "hook_mechanism": False,
      "hook_trust": "not-configured",
      "hooks": False,
      "installed": installed,
      "provider": "gemini",
      "sandbox": False,
      "skill": False,
      "version": metadata.get ("version"),
   })
   levels = { "none": 0, "guided": 1, "guarded": 2, "sandboxed": 3 }
   configured = str (repo.get ("agent:enforcement", "guarded")) if git.is_repo () else "guarded"
   ok = all (
      levels.get (value ["effective_enforcement"], 0) >= levels.get (configured, 2)
      for value in providers if value ["hook_mechanism"]
   )
   return {
      "configured_enforcement": configured,
      "guard_drift": _guard_drift (install),
      "ok": ok,
      "providers": providers,
   }


def doctor (
   agents: Annotated [bool, typer.Option ("--agents", help="Validate Codex and Claude adapters")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
):
   """Check tools and configuration.

   Verifies that required (git) and optional (claude, ollama, gh) tools are
   installed, shows their versions, and confirms at least one AI provider is
   available. Also displays the active provider and model settings from
   ~/.config/imp/config.json.
   """

   if agents:
      data = _agent_report ()
      if json_output or runtime.options.json:
         result.emit ("imp.doctor-agents.v1", "imp doctor --agents", data, json_output=True, ok=data ["ok"])
      else:
         console.header ("Agent adapters")
         console.table (
            [ "Provider", "Skill", "Context", "Bootstrap", "Guards", "Trust", "Sandbox", "Effective" ],
            [
               [
                  value ["provider"],
                  "yes" if value ["skill"] else "no",
                  "yes" if value ["context_injection"] else "no",
                  "yes" if value ["automatic_bootstrap"] else "no",
                  "yes" if value ["guards"] else "no",
                  value ["hook_trust"],
                  "no",
                  value ["effective_enforcement"],
               ]
               for value in data ["providers"]
            ],
         )
         console.muted (f"Required: {data ['configured_enforcement']}")
         for value in data ["providers"]:
            if value ["hook_trust"] == "review-required":
               console.hint ("Codex: run /hooks and trust the Imp hooks")
            missing = [ event for event, present in value ["events"].items () if not present ]
            if missing:
               console.warn (f"{value ['provider']}: guard hook missing events: {', '.join (missing)}")
         if data ["guard_drift"] == "modified":
            console.warn ("Deployed agent guard differs from the packaged adapter; rerun adapters/install.py")
      if not data ["ok"]:
         raise typer.Exit (1)
      return data

   console.header ("Doctor")

   ok = True
   ok = _check ("git", "git", "https://git-scm.com") and ok
   _check ("claude", "claude", "https://claude.ai/install.sh", required=False)
   _check ("ollama", "ollama", "https://ollama.com", required=False)
   _check ("gh", "gh", "https://cli.github.com", required=False)

   console.out.print ()

   has_claude = shutil.which ("claude") is not None
   has_ollama = shutil.which ("ollama") is not None

   if not has_claude and not has_ollama:
      console.err ("No AI provider found (need claude or ollama)")
      ok = False

   cfg = config.load ()
   provider = cfg ["provider"]
   console.muted (f"Provider: {provider}")
   console.muted (f"Fast model: {cfg ['model:fast']}")
   console.muted (f"Smart model: {cfg ['model:smart']}")
   console.muted (f"Config: {config.path ()}")

   console.out.print ()

   if has_claude or has_ollama:
      if console.spin ("Testing AI connection...", ai.ping):
         console.success ("AI responding")
      else:
         console.err ("AI not responding")
         if provider == "claude":
            console.hint ("run: claude to authenticate")
         else:
            console.hint ("is ollama running? try: ollama serve")
         ok = False

   console.out.print ()

   if ok:
      console.success ("All good")
   else:
      console.warn ("Some issues found")
      raise typer.Exit (1)
   return { "ok": ok }
