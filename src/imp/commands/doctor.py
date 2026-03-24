import shutil
import subprocess

import typer

from imp import ai, config, console


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
   ~/.config/imp/config.json.
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
