import json
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from imp import __version__, console


def _run (*args: str) -> subprocess.CompletedProcess [str]:
   return subprocess.run (
      list (args),
      capture_output=True,
      text=True,
      timeout=300,
   )

def _direct_url () -> dict:
   try:
      raw = metadata.distribution ("imp-git").read_text ("direct_url.json")
   except metadata.PackageNotFoundError:
      return {}

   if not raw:
      return {}

   try:
      return json.loads (raw)
   except json.JSONDecodeError:
      return {}

def _source_repo (info: dict) -> str:
   if not info.get ("dir_info", {}).get ("editable"):
      return ""

   url = info.get ("url", "")
   if not url.startswith ("file://"):
      return ""

   return url.removeprefix ("file://")

def _vcs_target (info: dict) -> str:
   vcs = info.get ("vcs_info", {}).get ("vcs", "")
   if not vcs:
      return ""

   url = info.get ("url", "")
   if not url:
      return ""

   rev = info.get ("vcs_info", {}).get ("requested_revision", "")
   return f"{vcs}+{url}@{rev}" if rev else f"{vcs}+{url}"

def _installer (info: dict) -> list [str]:
   target = _vcs_target (info) or "imp-git"

   try:
      location = str (metadata.distribution ("imp-git").locate_file (""))
   except metadata.PackageNotFoundError:
      location = ""

   if "/pipx/" in location and shutil.which ("pipx"):
      return [ "pipx", "upgrade", "imp-git" ]

   if "/uv/tools/" in location and shutil.which ("uv"):
      return [ "uv", "tool", "upgrade", "imp-git" ]

   return [ sys.executable, "-m", "pip", "install", "--upgrade", target ]

def _fresh_version () -> str:
   result = _run (
      sys.executable, "-c",
      "from importlib.metadata import version; print (version ('imp-git'))",
   )
   return result.stdout.strip () or __version__

def _pull (repo: str) -> str:
   result = _run ("git", "-C", repo, "pull", "--ff-only")

   if result.returncode != 0:
      console.err ((result.stderr or result.stdout).strip ())
      console.fatal ("Pull failed")

   return result.stdout.strip ()

def _reinstall (repo: str):
   result = _run (sys.executable, "-m", "pip", "install", "-e", repo, "--quiet")
   if result.returncode == 0:
      return

   if shutil.which ("uv"):
      result = _run ("uv", "pip", "install", "-e", repo, "--quiet", "--python", sys.executable)
      if result.returncode == 0:
         return

   console.warn ("Source updated but reinstall failed, version metadata may lag")

def update ():
   """Update imp to the latest version.

   Editable installs pull their source repo and reinstall. Package
   installs upgrade through whichever installer owns imp (pipx,
   uv tool, or pip).
   """

   console.header ("Update")

   console.label ("Current")
   console.item (__version__)
   console.out.print ()

   info = _direct_url ()
   repo = _source_repo (info)

   if repo:
      if not Path (repo, ".git").exists ():
         console.fatal (f"Source repo not found at {repo}")

      console.muted (f"Editable install from {repo}")
      console.out.print ()

      console.spin ("Pulling source...", _pull, repo)
      console.spin ("Reinstalling...", _reinstall, repo)
   else:
      cmd = _installer (info)
      result = console.spin ("Upgrading...", _run, *cmd)

      if result.returncode != 0:
         console.err ((result.stderr or result.stdout).strip ())
         console.fatal ("Upgrade failed")

   fresh = _fresh_version ()

   console.out.print ()

   if fresh == __version__:
      console.success ("Already up to date")
      return

   console.success (f"Updated {__version__} → {fresh}")
