import importlib.util
import json
from pathlib import Path

from imp_git.commands import doctor


def _guard ():
   path = Path (__file__).parents [1] / "adapters" / "agent_guard.py"
   spec = importlib.util.spec_from_file_location ("imp_agent_guard", path)
   assert spec and spec.loader
   module = importlib.util.module_from_spec (spec)
   spec.loader.exec_module (module)
   return module


def test_actor_identity_is_stable_and_namespaced ():
   guard = _guard ()

   assert guard._actor ("codex", "Thread 123") == "actor:codex:thread-123"


def test_raw_git_mutations_are_detected_but_reads_are_not ():
   guard = _guard ()

   assert guard._git_mutation ("git commit -m test") == "commit"
   assert guard._git_mutation ("cd app && git push origin main") == "push"
   assert guard._git_mutation ("git status") == ""


def test_repository_instruction_file_write_is_denied (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Write",
         "tool_input": { "file_path": str (tmp_path / "AGENTS.md") },
      },
      "codex",
   )

   assert output [0] [0] == "PreToolUse"
   assert "forbidden" in output [0] [1] ["deny"]


def test_repository_instruction_file_read_is_allowed (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Bash",
         "tool_input": { "command": "sed -n '1,200p' AGENTS.md" },
      },
      "codex",
   )

   assert output == []


def test_raw_git_write_is_denied_before_repository_discovery (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Bash",
         "tool_input": { "command": "git reset --hard HEAD~1" },
      },
      "codex",
   )

   assert "Raw `git reset` is blocked" in output [0] [1] ["deny"]


def test_non_repository_writes_are_allowed (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))
   monkeypatch.setattr (guard, "_status", lambda path: (_ for _ in ()).throw (AssertionError (path)))

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Write",
         "tool_input": { "file_path": str (tmp_path / "notes.md") },
      },
      "codex",
   )
   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "apply_patch",
         "tool_input": { "command": "*** Add File: draft.txt\n+hello\n" },
      },
      "codex",
   )

   assert output == []


def test_repository_inspection_failure_is_denied (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   (tmp_path / ".git").mkdir ()
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))
   monkeypatch.setattr (guard, "_status", lambda path: None)

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Write",
         "tool_input": { "file_path": str (tmp_path / "source.py") },
      },
      "codex",
   )

   assert "could not inspect this Git repository" in output [0] [1] ["deny"]


def test_write_across_repository_boundary_is_denied (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   repository = tmp_path / "repository"
   (repository / ".git").mkdir (parents=True)
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "apply_patch",
         "tool_input": {
            "command": "*** Update File: notes.md\n*** Update File: repository/source.py\n",
         },
      },
      "codex",
   )

   assert "cross Git repository boundaries" in output [0] [1] ["deny"]


def test_registered_temper_workspace_is_discovered (tmp_path, monkeypatch):
   guard = _guard ()
   config = tmp_path / "config"
   workspace = tmp_path / "workspace"
   repository = tmp_path / "repositories" / "api"
   repository.mkdir (parents=True)
   registry = config / "temper" / "workspaces.json"
   mapping = config / "temper" / "workspaces" / "demo" / "repositories.json"
   mapping.parent.mkdir (parents=True)
   registry.parent.mkdir (parents=True, exist_ok=True)
   registry.write_text (json.dumps ({ "workspaces": { "demo": str (workspace) } }))
   mapping.write_text (json.dumps ({ "repositories": { "api": str (repository) } }))
   monkeypatch.setenv ("XDG_CONFIG_HOME", str (config))

   assert guard._workspace (repository) == workspace.resolve ()


def test_codex_guard_requires_all_enabled_trusted_hooks (monkeypatch):
   hooks = [
      {
         "command": "python3 /home/test/.config/katforge/agents/agent_guard.py codex",
         "enabled": True,
         "eventName": event,
         "trustStatus": "trusted",
      }
      for event in [ "preToolUse", "sessionEnd", "sessionStart" ]
   ]
   monkeypatch.setattr (doctor, "_codex_hooks", lambda cwd: hooks)

   assert doctor._codex_guard (Path.cwd ()) == (True, "trusted")

   hooks [0] ["trustStatus"] = "modified"

   assert doctor._codex_guard (Path.cwd ()) == (False, "review-required")
