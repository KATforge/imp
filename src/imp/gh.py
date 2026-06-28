import json
import shutil
import subprocess

from imp import console

def available () -> bool:
   return shutil.which ("gh") is not None

def require ():
   if not available ():
      console.hint ("https://cli.github.com")
      console.fatal ("GitHub CLI (gh) not installed")

def issue (number: int) -> dict:
   try:
      result = subprocess.run (
         [ "gh", "issue", "view", str (number), "--json", "title,body,labels" ],
         capture_output=True,
         text=True,
         check=True,
         timeout=30,
      )
      return json.loads (result.stdout)
   except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as e:
      console.fatal (f"Could not fetch issue #{number}: {e}")

def pr_create (title: str, body: str, base: str, head: str) -> str:
   result = subprocess.run (
      [
         "gh", "pr", "create",
         "--title", title,
         "--body", body,
         "--base", base,
         "--head", head,
      ],
      capture_output=True,
      text=True,
      check=True,
      timeout=30,
   )
   return result.stdout.strip ()

def release_create (ver: str, notes: str, prerelease: bool = False) -> bool:
   try:
      cmd = [
         "gh", "release", "create",
         f"v{ver}",
         "--title", f"v{ver}",
         "--notes", notes,
      ]
      if prerelease:
         cmd.append ("--prerelease")

      subprocess.run (
         cmd,
         capture_output=True,
         text=True,
         check=True,
         timeout=30,
      )
      return True
   except subprocess.CalledProcessError:
      return False
