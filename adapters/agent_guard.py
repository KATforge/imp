#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_GIT_MUTATIONS = {
   "add", "am", "apply", "branch", "checkout", "cherry-pick", "clean", "commit",
   "merge", "mv", "pull", "push", "rebase", "reset", "restore", "revert", "rm",
   "stash", "switch", "tag", "update-ref",
}
_INSTRUCTION_FILES = { "AGENTS.MD", "CLAUDE.MD", "CODEX.MD" }
_READ_COMMANDS = re.compile (
   r"^\s*(?:pwd|ls|find|rg|grep|head|tail|wc|which|command\s+-v|sed\s+-n|"
   r"imp\s+(?:status|diff|log|show|blame|active)|temper\s+(?:status|change\s+status))\b"
)


def _emit (event: str, *, context: str = "", deny: str = ""):
   output: dict [str, Any] = { "hookSpecificOutput": { "hookEventName": event } }
   specific = output ["hookSpecificOutput"]
   if context:
      specific ["additionalContext"] = context [:9000]
   if deny:
      specific ["permissionDecision"] = "deny"
      specific ["permissionDecisionReason"] = deny
   print (json.dumps (output))


def _run (*args: str) -> dict [str, Any] | None:
   executable = shutil.which (args [0])
   if not executable:
      return None
   result = subprocess.run ([ executable, *args [1:] ], capture_output=True, text=True, timeout=20, check=False)
   if result.returncode:
      return None
   try:
      return json.loads (result.stdout)
   except json.JSONDecodeError:
      return None


def _status (path: Path) -> dict [str, Any] | None:
   value = _run ("imp", "-C", str (path), "--json", "status")
   return value.get ("data") if value else None


def _workspace (path: Path) -> Path | None:
   for parent in [ path, *path.parents ]:
      if (parent / "temper.yaml").is_file ():
         return parent
   config = Path (os.environ.get ("XDG_CONFIG_HOME", str (Path.home () / ".config"))) / "temper"
   try:
      registry = json.loads ((config / "workspaces.json").read_text ())
   except (FileNotFoundError, json.JSONDecodeError, OSError):
      return None
   matches = []
   resolved = path.resolve ()
   for name, root in registry.get ("workspaces", {}).items ():
      try:
         values = json.loads ((config / "workspaces" / name / "repositories.json").read_text ())
      except (FileNotFoundError, json.JSONDecodeError, OSError):
         continue
      if any (
         resolved == Path (repository).resolve () or resolved.is_relative_to (Path (repository).resolve ())
         for repository in values.get ("repositories", {}).values ()
      ):
         matches.append (Path (root).resolve ())
   return matches [0] if len (set (matches)) == 1 else None


def _actor (provider: str, session_id: str) -> str:
   segment = re.sub (r"[^a-zA-Z0-9._-]+", "-", session_id).strip ("-._").lower () or "session"
   return f"actor:{provider}:{segment}"


def _state_path (provider: str, session_id: str) -> Path:
   root = Path (os.environ.get ("XDG_STATE_HOME", str (Path.home () / ".local/state")))
   safe = re.sub (r"[^a-zA-Z0-9._-]+", "-", session_id)
   return root / "imp" / "agents" / provider / f"{safe}.json"


def _write_state (provider: str, session_id: str, value: dict [str, Any]):
   path = _state_path (provider, session_id)
   path.parent.mkdir (parents=True, exist_ok=True)
   temporary = path.with_suffix (".tmp")
   temporary.write_text (json.dumps (value, indent=3, sort_keys=True) + "\n")
   temporary.chmod (0o600)
   temporary.replace (path)


def _read_state (provider: str, session_id: str) -> dict [str, Any] | None:
   try:
      return json.loads (_state_path (provider, session_id).read_text ())
   except (FileNotFoundError, json.JSONDecodeError, OSError):
      return None


def _feature_for (status: dict [str, Any], path: Path) -> dict [str, Any] | None:
   resolved = path.resolve ()
   for feature in status.get ("features", []):
      root = Path (str (feature ["path"])).resolve ()
      if resolved == root or resolved.is_relative_to (root):
         return feature
   return None


def _paths (event: dict [str, Any]) -> list [Path]:
   tool = str (event.get ("tool_name", ""))
   values = event.get ("tool_input", {}) or {}
   cwd = Path (str (event.get ("cwd") or Path.cwd ())).resolve ()
   if tool in { "Edit", "Write" }:
      raw = str (values.get ("file_path") or values.get ("path") or "")
      return [Path (raw) if Path (raw).is_absolute () else cwd / raw] if raw else []
   if tool == "apply_patch":
      command = str (values.get ("command", ""))
      found = re.findall (r"^\*\*\* (?:Add|Update|Delete) File:\s+(.+)$", command, flags=re.M)
      return [Path (raw) if Path (raw).is_absolute () else cwd / raw for raw in found]
   return []


def _git_mutation (command: str) -> str:
   for match in re.finditer (r"(?:^|[;&|]\s*|\bsudo\s+)git\s+([a-z-]+)", command):
      if match.group (1) in _GIT_MUTATIONS:
         return match.group (1)
   return ""


def _bash_path (event: dict [str, Any]) -> Path:
   values = event.get ("tool_input", {}) or {}
   configured = str (values.get ("workdir") or "")
   if configured:
      return Path (configured).expanduser ().resolve ()
   command = str (values.get ("command", ""))
   match = re.match (r"\s*cd\s+(['\"]?)([^\s;&|]+)\1\s*(?:&&|;)", command)
   if match:
      return Path (match.group (2)).expanduser ().resolve ()
   return Path (str (event.get ("cwd") or Path.cwd ())).resolve ()


def _repository (path: Path) -> Path | None:
   current = path if path.is_dir () else path.parent
   for parent in [ current, *current.parents ]:
      if (parent / ".git").exists ():
         return parent
   return None


def _attach (
   provider: str,
   session_id: str,
   actor: str,
   feature: dict [str, Any],
) -> tuple [bool, str]:
   value = _run (
      "imp", "-C", str (feature ["path"]), "--actor-id", actor, "--json",
      "context", str (feature ["feature_id"]),
   )
   if not value:
      return False, f"Cannot acquire `{feature ['feature_id']}`. Resolve its Imp writer claim first."
   data = value ["data"]
   _write_state (provider, session_id, {
      "actor_id": actor,
      "context": data ["context"],
      "feature_id": data ["feature_id"],
      "path": data ["path"],
   })
   return True, Path (str (data ["context"])).read_text ()


def _session_start (event: dict [str, Any], provider: str):
   cwd = Path (str (event.get ("cwd") or Path.cwd ())).resolve ()
   status = _status (cwd)
   if not status:
      return
   session_id = str (event.get ("session_id") or "session")
   actor = _actor (provider, session_id)
   feature = _feature_for (status, cwd)
   workspace = _workspace (cwd)
   lines = [
      "KATforge development policy is active.",
      f"Resolved actor: `{actor}`.",
      "Use Imp for every Git operation.",
      "Before the first source mutation, attach to a managed Imp feature and use its returned path.",
   ]
   if feature:
      lines.append (f"Current managed feature: `{feature ['feature_id']}` at `{feature ['path']}`.")
   if workspace:
      lines.append (f"Temper workspace detected at `{workspace}`. Use Temper only for coupled source or runtime work.")
   _emit ("SessionStart", context="\n".join (lines))


def _pre_tool (event: dict [str, Any], provider: str):
   tool = str (event.get ("tool_name", ""))
   values = event.get ("tool_input", {}) or {}
   session_id = str (event.get ("session_id") or "session")
   actor = _actor (provider, session_id)
   command = str (values.get ("command", "")) if tool == "Bash" else ""
   mutation = _git_mutation (command)
   if mutation:
      _emit (
         "PreToolUse",
         deny=f"Raw `git {mutation}` is blocked. Use the equivalent `imp {mutation}` workflow.",
      )
      return
   if tool == "Bash" and re.search (r"\bgh\s+(?:pr\s+(?:create|merge)|release\s+create)\b", command):
      _emit ("PreToolUse", deny="Direct GitHub publication is blocked. Use `imp done --pr` or `imp ship`.")
      return
   paths = _paths (event)
   if any (path.name.upper () in _INSTRUCTION_FILES for path in paths):
      _emit ("PreToolUse", deny="Repository agent-instruction files are forbidden. Use ephemeral Imp context.")
      return
   if tool == "Bash" and (command.lstrip ().startswith ("imp ") or command.lstrip ().startswith ("temper ")):
      return
   if tool == "Bash" and _READ_COMMANDS.match (command):
      return
   if any (name in command.upper () for name in _INSTRUCTION_FILES):
      _emit ("PreToolUse", deny="Repository agent-instruction files are forbidden. Use ephemeral Imp context.")
      return
   if tool not in { "Bash", "Edit", "Write", "apply_patch" }:
      return
   targets = paths or [ _bash_path (event) ]
   repositories = [ repository for target in targets if (repository := _repository (target)) ]
   if not repositories:
      return
   if len (repositories) != len (targets) or len (set (repositories)) != 1:
      _emit ("PreToolUse", deny="Split writes that cross Git repository boundaries into separate operations.")
      return
   status = _status (repositories [0])
   if not status:
      _emit (
         "PreToolUse",
         deny="Imp could not inspect this Git repository. Run `imp status --json`, then initialize Imp if needed.",
      )
      return
   target = targets [0]
   feature = _feature_for (status, target)
   if not feature:
      hint = (
         f"Source mutation is blocked until Imp creates a worktree. Run `imp start <name> --task <intent> "
         f"--use --actor-id {actor} --yes --json`, capture its returned path, and retry only there."
      )
      _emit ("PreToolUse", deny=hint)
      return
   assigned = _read_state (provider, session_id)
   if assigned and assigned.get ("feature_id") != feature ["feature_id"]:
      _emit (
         "PreToolUse",
         deny=f"This session is assigned to `{assigned ['feature_id']}` at `{assigned ['path']}`.",
      )
      return
   ok, context = _attach (provider, session_id, actor, feature)
   if not ok:
      _emit ("PreToolUse", deny=context)
      return
   if any (not path.resolve ().is_relative_to (Path (str (feature ["path"])).resolve ()) for path in paths):
      _emit ("PreToolUse", deny=f"Writes are limited to `{feature ['path']}`.")
      return
   _emit ("PreToolUse", context=context)


def _session_end (event: dict [str, Any], provider: str):
   session_id = str (event.get ("session_id") or "session")
   assigned = _read_state (provider, session_id)
   if not assigned:
      return
   _run (
      "imp", "-C", str (assigned ["path"]), "--actor-id", str (assigned ["actor_id"]),
      "worktree", "release", str (assigned ["feature_id"]),
   )
   _state_path (provider, session_id).unlink (missing_ok=True)


def main () -> int:
   provider = sys.argv [1] if len (sys.argv) > 1 else "agent"
   try:
      event = json.load (sys.stdin)
      name = str (event.get ("hook_event_name", ""))
      if name == "SessionStart":
         _session_start (event, provider)
      elif name == "PreToolUse":
         _pre_tool (event, provider)
      elif name == "SessionEnd":
         _session_end (event, provider)
   except Exception as error:
      if str ((locals ().get ("event") or {}).get ("hook_event_name")) == "PreToolUse":
         _emit ("PreToolUse", deny=f"KATforge guard failed closed: {error}")
         return 0
      print (f"KATforge adapter warning: {error}", file=sys.stderr)
   return 0


if __name__ == "__main__":
   raise SystemExit (main ())
