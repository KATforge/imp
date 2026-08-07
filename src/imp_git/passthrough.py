import subprocess

from imp_git import console


def run (args: list [str]) -> int:
   """Run Git with untouched arguments and inherited terminal streams."""

   try:
      result = subprocess.run ([ "git", *args ], check=False)
   except OSError as error:
      console.err (f"Could not run git: {error}")
      return 127

   return result.returncode
