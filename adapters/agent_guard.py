#!/usr/bin/env python3
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

_GIT_OPTION_VALUES = { "-C", "-c", "--exec-path", "--git-dir", "--namespace", "--work-tree" }
_ENV_ASSIGNMENT = re.compile (r"[A-Za-z_][A-Za-z0-9_]*=.*")
_SHELLS = { "bash", "dash", "ksh", "sh", "zsh" }
_WRAPPERS = { "command", "env", "nice", "nohup", "setsid", "stdbuf", "sudo", "time", "xargs" }


def _emit (event: str, *, context: str = ""):
   output: dict [str, Any] = { "hookSpecificOutput": { "hookEventName": event } }
   if context:
      output ["hookSpecificOutput"] ["additionalContext"] = context [:9000]
   print (json.dumps (output))


def _command (event: dict [str, Any]) -> str:
   values = event.get ("tool_input", {}) or {}
   return str (values.get ("command") or "")


def _segments (command: str) -> list [list [str]]:
   pieces = []
   current = []
   quote = ""
   escaped = False
   for char in command:
      if escaped:
         current.append (char)
         escaped = False
         continue
      if char == "\\" and quote != "'":
         current.append (char)
         escaped = True
         continue
      if quote:
         current.append (char)
         if char == quote:
            quote = ""
         continue
      if char in "'\"":
         quote = char
         current.append (char)
         continue
      if char in "\n;|&`()":
         pieces.append ("".join (current))
         current = []
         continue
      current.append (char)
   pieces.append ("".join (current))
   values = []
   for piece in pieces:
      stripped = piece.strip ()
      if not stripped:
         continue
      try:
         tokens = shlex.split (stripped)
      except ValueError:
         tokens = stripped.split ()
      if tokens:
         values.append (tokens)
   return values


def _substitutions (command: str) -> list [str]:
   values = []
   index = 0
   single = False
   while index < len (command):
      char = command [index]
      if char == "\\" and not single:
         index += 2
         continue
      if char == "'":
         single = not single
         index += 1
         continue
      if not single and char == "`":
         end = command.find ("`", index + 1)
         if end < 0:
            break
         values.append (command [index + 1:end])
         index = end + 1
         continue
      if not single and command.startswith ("$(", index):
         depth = 1
         scan = index + 2
         while scan < len (command) and depth:
            if command [scan] == "(":
               depth += 1
            elif command [scan] == ")":
               depth -= 1
            scan += 1
         if depth:
            break
         values.append (command [index + 2:scan - 1])
         index = scan
         continue
      index += 1
   return values


def _strip_wrappers (tokens: list [str]) -> list [str]:
   while tokens:
      if _ENV_ASSIGNMENT.fullmatch (tokens [0]):
         tokens = tokens [1:]
         continue
      if Path (tokens [0]).name in _WRAPPERS:
         tokens = tokens [1:]
         while tokens and tokens [0].startswith ("-"):
            tokens = tokens [1:]
         continue
      break
   return tokens


def _call (tokens: list [str], option_values: set [str]) -> tuple [str, list [str]]:
   index = 1
   while index < len (tokens):
      value = tokens [index]
      if value in option_values:
         index += 2
         continue
      if value.startswith ("-"):
         index += 1
         continue
      return value, tokens [index + 1:]
   return "", []


def _shell_payload (tokens: list [str]) -> str:
   for index, value in enumerate (tokens [1:], 1):
      if not value.startswith ("-"):
         return ""
      if "c" in value and index + 1 < len (tokens):
         return tokens [index + 1]
   return ""


# Static, name-based detection cannot see through renamed or symlinked git
# binaries, such as `ln -s $(which git) g; ./g push`. OS-level sandboxing is
# the real hard boundary; this scanner only raises the cost of casual bypass.
def _git_invocation (command: str) -> str:
   for inner in _substitutions (command):
      value = _git_invocation (inner)
      if value:
         return value
   for tokens in _segments (command):
      stripped = _strip_wrappers (tokens)
      if not stripped:
         continue
      name = Path (stripped [0]).name
      if name in _SHELLS:
         payload = _shell_payload (stripped)
         value = _git_invocation (payload) if payload else ""
         if value:
            return value
         continue
      if name != "git":
         continue
      subcommand, _rest = _call (stripped, _GIT_OPTION_VALUES)
      return subcommand or "git"
   return ""


def _pre_tool (event: dict [str, Any]):
   if str (event.get ("tool_name", "")) != "Bash":
      return
   verb = _git_invocation (_command (event))
   if not verb:
      return
   detected = "git" if verb == "git" else f"git {verb}"
   _emit ("PreToolUse", context=(
      f"Raw `{detected}` detected. Prefer the Imp workflow: `imp commit`, `imp done`, `imp ship`, "
      "`imp status`, `imp log`, `imp diff`. (Reminder only; the command is allowed.)"
   ))


def main () -> int:
   try:
      event = json.load (sys.stdin)
      if str (event.get ("hook_event_name", "")) == "PreToolUse":
         _pre_tool (event)
   except Exception as error:
      print (f"Imp adapter warning: {error}", file=sys.stderr)
   return 0


if __name__ == "__main__":
   raise SystemExit (main ())
