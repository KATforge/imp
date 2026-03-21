import os
import shutil
import subprocess

import typer

from imp import console


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


def doctor ():
   """Check tools and configuration.

   Verifies that required (git) and optional (claude, ollama, gh) tools are
   installed, shows their versions, and confirms at least one AI provider is
   available. Also displays the active provider and model settings from
   IMP_AI_PROVIDER, IMP_AI_MODEL_FAST, and IMP_AI_MODEL_SMART.
   """

   console.header ("Doctor")

   ok = True
   ok = _check ("git", "git", "https://git-scm.com") and ok
   _check ("claude", "claude", "https://docs.anthropic.com/en/docs/claude-code", required=False)
   _check ("ollama", "ollama", "https://ollama.com", required=False)
   _check ("gh", "gh", "https://cli.github.com", required=False)

   console.out.print ()

   has_claude = shutil.which ("claude") is not None
   has_ollama = shutil.which ("ollama") is not None

   if not has_claude and not has_ollama:
      console.err ("No AI provider found (need claude or ollama)")
      ok = False

   provider = os.environ.get ("IMP_AI_PROVIDER", "")
   console.muted (f"Provider: {provider or 'claude (default)'}")

   fast = os.environ.get ("IMP_AI_MODEL_FAST", "")
   if fast:
      console.muted (f"Fast model: {fast}")

   smart = os.environ.get ("IMP_AI_MODEL_SMART", "")
   if smart:
      console.muted (f"Smart model: {smart}")

   console.out.print ()

   if ok:
      console.success ("All good")
   else:
      console.warn ("Some issues found")
      raise typer.Exit (1)
