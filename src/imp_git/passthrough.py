import subprocess

from imp_git import console, git

_EXPLICIT_PUSH_FLAGS = { "-u", "--set-upstream", "--all", "--mirror", "--delete", "-d" }


def _smart_push (args: list [str]) -> list [str]:
   """Default a bare `push` to track the current branch instead of an upstream error."""

   if not args or args [0] != "push":
      return args

   options = args [1:]
   if any (value in _EXPLICIT_PUSH_FLAGS or not value.startswith ("-") for value in options):
      return args
   if git.has_upstream ():
      return args

   branch = git.branch ()
   if not branch:
      return args

   return [ "push", "-u", "origin", branch, *options ]


def run (args: list [str]) -> int:
   """Run Git with untouched arguments and inherited terminal streams, except a bare push tracks its branch."""

   try:
      result = subprocess.run ([ "git", *_smart_push (args) ], check=False)
   except OSError as error:
      console.err (f"Could not run git: {error}")
      return 127

   return result.returncode
