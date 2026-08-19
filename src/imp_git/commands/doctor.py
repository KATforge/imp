import shutil
import subprocess
from pathlib import Path
from typing import Any

import typer

from imp_git import ai, config, console, git, result, runtime

TOOLS = [
   { "command": "git", "name": "git", "required": True, "url": "https://git-scm.com" },
   { "command": "claude", "name": "claude", "required": False, "url": "https://claude.ai/install.sh" },
   { "command": "ollama", "name": "ollama", "required": False, "url": "https://ollama.com" },
   { "command": "gh", "name": "gh", "required": False, "url": "https://cli.github.com" },
]
PROVIDERS = { "claude", "ollama" }


def _version (command: str) -> str:
   try:
      found = subprocess.run ([ command, "--version" ], capture_output=True, text=True, timeout=5)
   except (subprocess.TimeoutExpired, OSError):
      return "installed"
   lines = found.stdout.strip ().splitlines ()

   return lines [0] if lines else "installed"


def _inspect () -> list [dict [str, Any]]:
   values = []
   for tool in TOOLS:
      present = shutil.which (str (tool ["command"])) is not None
      values.append ({ **tool, "present": present, "version": _version (str (tool ["command"])) if present else "" })

   return values


def _report (tools: list [dict [str, Any]]):
   for tool in tools:
      if tool ["present"]:
         console.success (f"{tool ['name']} ({tool ['version']})")
         continue
      if tool ["required"]:
         console.err (f"{tool ['name']} not found")
      else:
         console.muted (f"  {tool ['name']} not found (optional)")
      console.item (str (tool ["url"]))


def _show_settings (settings: dict [str, Any]):
   console.label ("Configuration")
   console.table ([ "Key", "Value" ], [ [ key, str (value) ] for key, value in sorted (settings.items ()) ])
   console.muted ("  Stored in Git configuration: git config [--global] imp.<key> <value>")
   console.out.print ()


def _sweep_legacy () -> str:
   """Remove pre-derivation state directories; every fact now lives in Git itself."""

   if not git.succeeds ("rev-parse", "--git-dir"):
      return ""
   common = Path (git.common_dir ())
   if not common.is_absolute ():
      common = Path (git.repo_root ()) / common
   legacy = common.resolve () / "imp"
   if not legacy.is_dir ():
      return ""
   shutil.rmtree (legacy, ignore_errors=True)
   return str (legacy)


def doctor ():
   """Check tools and configuration, ping the AI provider, and sweep legacy state.

   Reports git, gh, and AI provider availability, shows the effective imp.* Git
   configuration, and sends one fixed ping to the provider. Inside a repository it
   also deletes any pre-Git-native .git/imp state directory. The ping is the only
   thing sent anywhere.
   """

   machine = runtime.options.json
   tools = _inspect ()
   settings = config.snapshot ()
   swept = _sweep_legacy ()
   missing = [ tool ["name"] for tool in tools if tool ["required"] and not tool ["present"] ]
   provider_found = any (tool ["present"] for tool in tools if tool ["name"] in PROVIDERS)

   if not machine:
      console.header ("Doctor")
      _report (tools)
      console.out.print ()
      if not provider_found:
         console.err ("No AI provider found (need claude or ollama)")
      _show_settings (settings)
      if swept:
         console.muted (f"Removed legacy state: {swept}")

   responding = None
   if provider_found:
      responding = console.spin ("Testing AI connection...", ai.ping) if not machine else ai.ping ()
      if not machine:
         if responding:
            console.success ("AI responding")
         else:
            console.err ("AI not responding")
            console.hint (
               "run: claude to authenticate" if settings ["provider"] == "claude"
               else "is ollama running? try: ollama serve"
            )
         console.out.print ()

   ok = not missing and provider_found and responding is not False
   data = {
      "configuration": settings,
      "legacy_removed": swept,
      "ok": ok,
      "provider_responding": responding,
      "tools": tools,
   }
   if machine:
      result.emit ("imp.doctor.v2", "imp doctor", data, json_output=True)
      if not ok:
         raise typer.Exit (1)
      return data

   if not ok:
      console.warn ("Some issues found")
      raise typer.Exit (1)
   console.success ("All good")

   return data
