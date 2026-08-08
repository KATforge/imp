import shutil
import subprocess

import typer

from imp_git import ai, config, console


def _check (name: str, command: str, url: str, required: bool = True) -> bool:
   if shutil.which (command):
      try:
         result = subprocess.run (
            [ command, "--version" ],
            capture_output=True,
            text=True,
            timeout=5,
         )
         version = result.stdout.strip ().splitlines () [0] if result.stdout.strip () else "installed"
      except (subprocess.TimeoutExpired, OSError):
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
   """Check required tools, optional AI providers, and configuration."""

   console.header ("Doctor")

   ok = _check ("git", "git", "https://git-scm.com")
   _check ("claude", "claude", "https://claude.ai/install.sh", required=False)
   _check ("ollama", "ollama", "https://ollama.com", required=False)
   _check ("gh", "gh", "https://cli.github.com", required=False)

   console.out.print ()

   has_claude = shutil.which ("claude") is not None
   has_ollama = shutil.which ("ollama") is not None
   if not has_claude and not has_ollama:
      console.err ("No AI provider found (need claude or ollama)")
      ok = False

   settings = config.load ()
   provider = settings ["provider"]
   console.muted (f"Provider: {provider}")
   console.muted (f"Fast model: {settings ['model:fast']}")
   console.muted (f"Smart model: {settings ['model:smart']}")
   console.muted (f"Config: {config.path ()}")

   console.out.print ()

   if has_claude or has_ollama:
      if console.spin ("Testing AI connection...", ai.ping):
         console.success ("AI responding")
      else:
         console.err ("AI not responding")
         hint = "run: claude to authenticate" if provider == "claude" else "is ollama running? try: ollama serve"
         console.hint (hint)
         ok = False

   console.out.print ()

   if not ok:
      console.warn ("Some issues found")
      raise typer.Exit (1)

   console.success ("All good")
   return { "ok": True }
