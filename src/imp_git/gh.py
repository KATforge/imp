import json
import shutil
import subprocess

from imp_git import state


def available () -> bool:
   return shutil.which ("gh") is not None


def _run (*args: str) -> str:
   try:
      result = subprocess.run (
         [ "gh", *args ], capture_output=True, text=True, timeout=30,
      )
   except OSError as error:
      raise state.StateError ("GitHub CLI failed") from error
   if result.returncode:
      raise state.StateError ((result.stderr or result.stdout).strip () or "GitHub CLI failed")
   return result.stdout.strip ()


def pr_view (head: str) -> dict:
   try:
      return json.loads (_run ("pr", "view", head, "--json", "url"))
   except (state.StateError, json.JSONDecodeError):
      return {}


def pr_create (title: str, body: str, base: str, head: str) -> str:
   return _run (
      "pr", "create", "--title", title, "--body", body, "--base", base, "--head", head,
   )


def pr_update (head: str, title: str, body: str):
   _run ("pr", "edit", head, "--title", title, "--body", body)


def release_create (tag: str, notes: str, prerelease: bool = False) -> str:
   args = [ "release", "create", tag, "--title", tag, "--notes", notes ]
   if prerelease:
      args.append ("--prerelease")
   return _run (*args)
