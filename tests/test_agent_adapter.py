import importlib.util
import json
from pathlib import Path

from typer.testing import CliRunner

from imp_git.commands import doctor
from imp_git.main import app


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

   for name in [ "AGENTS.md", "CLAUDE.md", "CODEX.md", "GEMINI.md", ".cursorrules", "copilot-instructions.md" ]:
      guard._pre_tool (
         {
            "hook_event_name": "PreToolUse",
            "session_id": "thread-1",
            "cwd": str (tmp_path),
            "tool_name": "Write",
            "tool_input": { "file_path": str (tmp_path / name) },
         },
         "codex",
      )

   assert len (output) == 6
   assert all (event == "PreToolUse" and "forbidden" in values ["deny"] for event, values in output)


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


def test_claude_guard_request_asks_for_human_approval (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   prepared = []
   (tmp_path / ".git").mkdir ()
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))
   monkeypatch.setattr (guard, "_prepare_guard", lambda *args: prepared.append (args) or True)

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Bash",
         "tool_input": { "command": "imp guard request direct-edit" },
      },
      "claude",
   )

   assert prepared [0] [0] == tmp_path
   assert output [0] [1] ["ask"].startswith ("Allow `actor:claude:thread-1`")


def test_codex_guard_request_waits_for_provider_permission (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   prepared = []
   (tmp_path / ".git").mkdir ()
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))
   monkeypatch.setattr (guard, "_prepare_guard", lambda *args: prepared.append (args) or True)

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Bash",
         "tool_input": { "command": "imp guard request direct-edit" },
      },
      "codex",
   )

   assert prepared == []
   assert "requires explicit provider approval" in output [0] [1] ["context"]


def test_permission_request_prepares_codex_grant (tmp_path, monkeypatch):
   guard = _guard ()
   prepared = []
   (tmp_path / ".git").mkdir ()
   monkeypatch.setattr (guard, "_prepare_guard", lambda *args: prepared.append (args) or True)

   guard._permission_request (
      {
         "hook_event_name": "PermissionRequest",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Bash",
         "tool_input": { "command": "imp guard request direct-edit" },
      },
      "codex",
   )

   assert prepared [0] == (
      tmp_path,
      "actor:codex:thread-1",
      "direct-edit",
      "codex",
      "thread-1",
   )


def test_direct_edit_grant_bypasses_only_worktree_requirement (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   (tmp_path / ".git").mkdir ()
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))
   monkeypatch.setattr (
      guard,
      "_grant",
      lambda *args: { "expires_at": "2026-08-07T01:00:00Z" },
   )
   monkeypatch.setattr (guard, "_status", lambda path: (_ for _ in ()).throw (AssertionError (path)))

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

   assert "Temporary direct-edit access is active" in output [0] [1] ["context"]


def test_guard_request_rejects_actor_spoofing (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   (tmp_path / ".git").mkdir ()
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Bash",
         "tool_input": {
            "command": "imp --actor-id actor:codex:other guard request direct-edit",
         },
      },
      "codex",
   )

   assert "must use this session's actor" in output [0] [1] ["deny"]


def test_internal_guard_commands_are_denied (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))

   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Bash",
         "tool_input": {
            "command": "imp guard prepare direct-edit --provider codex --session-id thread-1",
         },
      },
      "codex",
   )

   assert "reserved for the provider hook" in output [0] [1] ["deny"]


def test_guard_request_write_and_session_cleanup_end_to_end (repo, monkeypatch, tmp_path):
   guard = _guard ()
   actor = "actor:codex:thread-1"
   output = []
   monkeypatch.setenv ("XDG_STATE_HOME", str (tmp_path / "state"))

   assert guard._prepare_guard (repo, actor, "direct-edit", "codex", "thread-1") is True
   approved = CliRunner ().invoke (
      app,
      [ "--actor-id", actor, "--json", "guard", "request", "direct-edit" ],
   )
   assert approved.exit_code == 0

   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))
   guard._pre_tool (
      {
         "hook_event_name": "PreToolUse",
         "session_id": "thread-1",
         "cwd": str (repo),
         "tool_name": "Write",
         "tool_input": { "file_path": str (repo / "source.py") },
      },
      "codex",
   )
   assert "Temporary direct-edit access is active" in output [0] [1] ["context"]

   guard._session_end ({ "session_id": "thread-1" }, "codex")
   assert guard._grant (repo, actor, "direct-edit") is None


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


def test_registered_temper_change_worktree_is_discovered (tmp_path, monkeypatch):
   guard = _guard ()
   config = tmp_path / "config"
   state = tmp_path / "state"
   workspace = tmp_path / "workspace"
   worktree = tmp_path / "worktrees" / "api"
   worktree.mkdir (parents=True)
   registry = config / "temper" / "workspaces.json"
   mapping = config / "temper" / "workspaces" / "demo" / "repositories.json"
   change = state / "temper" / "workspaces" / "demo" / "changes" / "change--checkout.json"
   mapping.parent.mkdir (parents=True)
   change.parent.mkdir (parents=True)
   registry.write_text (json.dumps ({ "workspaces": { "demo": str (workspace) } }))
   mapping.write_text (json.dumps ({ "repositories": {} }))
   change.write_text (json.dumps ({ "members": { "api": { "path": str (worktree) } } }))
   monkeypatch.setenv ("XDG_CONFIG_HOME", str (config))
   monkeypatch.setenv ("XDG_STATE_HOME", str (state))

   assert guard._workspace (worktree) == workspace.resolve ()


def test_session_start_repairs_temper_local_state (tmp_path, monkeypatch):
   guard = _guard ()
   output = []
   calls = []
   (tmp_path / "temper.yaml").write_text ("name: demo\n")
   monkeypatch.setattr (guard, "_status", lambda _path: { "features": [] })
   monkeypatch.setattr (guard, "_run", lambda *args: calls.append (args) or { "ok": True })
   monkeypatch.setattr (guard, "_emit", lambda event, **values: output.append ((event, values)))

   guard._session_start (
      { "hook_event_name": "SessionStart", "session_id": "thread-1", "cwd": str (tmp_path) },
      "codex",
   )

   assert ("temper", "--workspace", str (tmp_path), "--json", "status") in calls
   assert "Temper workspace detected" in output [0] [1] ["context"]


def test_guard_allows_coupled_repositories_in_one_temper_change (tmp_path, monkeypatch):
   guard = _guard ()
   context = tmp_path / "context.md"
   context.write_text ("context")
   written = []
   monkeypatch.setattr (
      guard,
      "_read_state",
      lambda *_args: {
         "features": {
            "feature:api": {
               "change_id": "change:checkout",
               "path": "/worktrees/api",
            }
         }
      },
   )
   monkeypatch.setattr (
      guard,
      "_run",
      lambda *_args: {
         "data": {
            "context": str (context),
            "feature_id": "feature:web",
            "path": "/worktrees/web",
         }
      },
   )
   monkeypatch.setattr (guard, "_write_state", lambda *_args: written.append (_args [-1]))

   ok, _message = guard._attach (
      "codex",
      "thread-1",
      "actor:codex:thread-1",
      {
         "change_id": "change:checkout",
         "feature_id": "feature:web",
         "path": "/worktrees/web",
      },
   )

   assert ok is True
   assert set (written [0] ["features"]) == { "feature:api", "feature:web" }


def test_guard_rejects_uncoordinated_second_repository (tmp_path, monkeypatch):
   guard = _guard ()
   context = tmp_path / "context.md"
   context.write_text ("context")
   monkeypatch.setattr (
      guard,
      "_read_state",
      lambda *_args: {
         "features": {
            "feature:api": {
               "change_id": "",
               "path": "/worktrees/api",
            }
         }
      },
   )
   monkeypatch.setattr (
      guard,
      "_run",
      lambda *_args: {
         "data": {
            "context": str (context),
            "feature_id": "feature:web",
            "path": "/worktrees/web",
         }
      },
   )

   ok, message = guard._attach (
      "codex",
      "thread-1",
      "actor:codex:thread-1",
      {
         "change_id": "",
         "feature_id": "feature:web",
         "path": "/worktrees/web",
      },
   )

   assert ok is False
   assert "Temper change" in message


def test_codex_guard_requires_all_enabled_trusted_hooks (monkeypatch):
   hooks = [
      {
         "command": "python3 /home/test/.config/imp/agents/agent_guard.py codex",
         "enabled": True,
         "eventName": event,
         "trustStatus": "trusted",
      }
      for event in [ "permissionRequest", "preToolUse", "sessionEnd", "sessionStart" ]
   ]
   monkeypatch.setattr (doctor, "_codex_hooks", lambda cwd: hooks)

   assert doctor._codex_guard (Path.cwd ()) == (True, "trusted")

   hooks [0] ["trustStatus"] = "modified"

   assert doctor._codex_guard (Path.cwd ()) == (False, "review-required")
