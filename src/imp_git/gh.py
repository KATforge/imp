import json
import shutil
import subprocess

from imp_git import console


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

def pr_edit (number: int, title: str, body: str) -> str:
   # REST instead of gh pr edit: its GraphQL query trips on deprecated
   # Projects (classic) fields (fails on gh <= 2.52)
   result = subprocess.run (
      [
         "gh", "api", f"repos/{{owner}}/{{repo}}/pulls/{number}",
         "-X", "PATCH",
         "-f", f"title={title}",
         "-f", f"body={body}",
      ],
      capture_output=True,
      text=True,
      check=True,
      timeout=30,
   )
   return json.loads (result.stdout).get ("html_url", "")

def pr_view (head: str) -> dict:
   try:
      result = subprocess.run (
         [ "gh", "pr", "view", head, "--json", "number,state,url" ],
         capture_output=True,
         text=True,
         check=True,
         timeout=30,
      )
      return json.loads (result.stdout)
   except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
      return {}

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


def release_view (tag: str) -> dict:
   try:
      result = subprocess.run (
         [ "gh", "release", "view", tag, "--json", "isPrerelease,url" ],
         capture_output=True,
         text=True,
         check=True,
         timeout=30,
      )
      return json.loads (result.stdout)
   except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
      return {}

def release_delete (tag: str) -> bool:
   """Delete the GitHub release for a full tag name (e.g. "v2.3.1"). The
   underlying git tag is deleted separately; this only removes the release
   object so it isn't left dangling. False when there was no release."""
   try:
      subprocess.run (
         [ "gh", "release", "delete", tag, "--yes" ],
         capture_output=True,
         text=True,
         check=True,
         timeout=30,
      )
      return True
   except subprocess.CalledProcessError:
      return False
