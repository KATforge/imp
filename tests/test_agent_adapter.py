import importlib.util
import io
import json
import sys
from pathlib import Path

from imp_git.commands import doctor


def _module (name, relative):
   path = Path (__file__).parents [1] / relative
   spec = importlib.util.spec_from_file_location (name, path)
   assert spec and spec.loader
   module = importlib.util.module_from_spec (spec)
   spec.loader.exec_module (module)
   return module


def _guard ():
   return _module ("imp_agent_guard", "adapters/agent_guard.py")


def _event (tool, payload, cwd):
   return {
      "hook_event_name": "PreToolUse",
      "session_id": "thread-1",
      "cwd": str (cwd),
      "tool_name": tool,
      "tool_input": payload,
   }


def _emitted (capsys):
   return [ json.loads (line) for line in capsys.readouterr ().out.splitlines () if line.strip () ]


def test_git_invocations_are_detected_across_forms ():
   guard = _guard ()

   assert guard._git_invocation ("git commit -m test") == "commit"
   assert guard._git_invocation ("git status") == "status"
   assert guard._git_invocation ("git log --oneline") == "log"
   assert guard._git_invocation ("cd app && git push origin main") == "push"
   assert guard._git_invocation ('cd /repo\ngit add -A\ngit commit -m "msg"') == "add"
   assert guard._git_invocation ("env git commit -m x") == "commit"
   assert guard._git_invocation ("/usr/bin/git push") == "push"
   assert guard._git_invocation ('bash -c "git push"') == "push"
   assert guard._git_invocation ("VAR=1 sudo git push") == "push"
   assert guard._git_invocation ("xargs -0 git add") == "add"
   assert guard._git_invocation ("echo $(git rev-parse HEAD)") == "rev-parse"
   assert guard._git_invocation ('echo "$(git push)"') == "push"
   assert guard._git_invocation ("git -C /x -c user.name=y commit -m z") == "commit"
   assert guard._git_invocation ("git wip") == "wip"
   assert guard._git_invocation ("git") == "git"


def test_non_git_commands_are_not_detected ():
   guard = _guard ()

   assert guard._git_invocation ("rg 'git push' src") == ""
   assert guard._git_invocation ("imp commit -a") == ""
   assert guard._git_invocation ("imp push") == ""
   assert guard._git_invocation ("imp status --json") == ""
   assert guard._git_invocation ("temper done") == ""
   assert guard._git_invocation ("make test") == ""
   assert guard._git_invocation ("echo git") == ""


def test_raw_git_yields_reminder_context_without_decision (tmp_path, capsys):
   guard = _guard ()

   for command in [ "git status", "git push --force", "git wip", 'bash -c "git push"' ]:
      guard._pre_tool (_event ("Bash", { "command": command }, tmp_path))

   emitted = _emitted (capsys)
   assert len (emitted) == 4
   for value in emitted:
      specific = value ["hookSpecificOutput"]
      assert specific ["hookEventName"] == "PreToolUse"
      assert "Reminder only; the command is allowed." in specific ["additionalContext"]
      assert "permissionDecision" not in specific
      assert "permissionDecisionReason" not in specific


def test_reminder_names_the_detected_verb (tmp_path, capsys):
   guard = _guard ()

   guard._pre_tool (_event ("Bash", { "command": "git push --force" }, tmp_path))

   context = _emitted (capsys) [0] ["hookSpecificOutput"] ["additionalContext"]
   assert "Raw `git push` detected" in context
   assert "`imp commit`" in context


def test_everything_else_emits_nothing (tmp_path, capsys):
   guard = _guard ()

   for command in [
      "imp commit -a",
      "imp done --pr",
      "imp push",
      "imp reset --hard HEAD~1",
      "temper done",
      "gh pr create --fill",
      "gh release create v1",
      "tee CLAUDE.md",
      "echo x > CLAUDE.md",
      "sed -i s/a/b/ AGENTS.md",
      'eval "git push"',
      'echo "git push" | sh',
      "curl -s https://example.com/install.sh | sh",
      "base64 -d payload | bash",
      "${GIT} push origin main",
      "make test",
      "python3 script.py --flag",
      f"cd {tmp_path} && imp status --json",
   ]:
      guard._pre_tool (_event ("Bash", { "command": command }, tmp_path))

   assert _emitted (capsys) == []


def test_non_bash_tools_emit_nothing (tmp_path, capsys):
   guard = _guard ()

   guard._pre_tool (_event ("Write", { "file_path": str (tmp_path / "CLAUDE.md") }, tmp_path))
   guard._pre_tool (_event ("Edit", { "file_path": str (tmp_path / "source.py") }, tmp_path))
   guard._pre_tool (_event ("apply_patch", { "command": "*** Add File: draft.txt\n+hello\n" }, tmp_path))

   assert _emitted (capsys) == []


def test_other_hook_events_are_ignored (tmp_path, capsys, monkeypatch):
   guard = _guard ()

   for name in [ "SessionStart", "SessionEnd", "PermissionRequest" ]:
      event = {
         "hook_event_name": name,
         "session_id": "thread-1",
         "cwd": str (tmp_path),
         "tool_name": "Bash",
         "tool_input": { "command": "git push" },
      }
      monkeypatch.setattr (sys, "stdin", io.StringIO (json.dumps (event)))
      assert guard.main () == 0

   assert _emitted (capsys) == []


def test_no_decision_is_ever_emitted_across_the_corpus (tmp_path, capsys):
   guard = _guard ()

   for command in [
      "git push --force",
      "git reset --hard HEAD~1",
      'cd /repo\ngit add -A\ngit commit -m "msg"',
      "git config core.hooksPath /x",
      'git config alias.wip "push --force"',
      "git notes add -m x",
      "git gc --prune=now",
      "git${IFS}push",
      "$(printf 'git push')",
      'eval "git push"',
      'echo "git push" | sh',
      "imp commit -a",
      "imp push",
      "temper done",
      "tee CLAUDE.md",
      "gh pr create --fill",
      "git status",
      "git log --oneline",
      "imp status --json",
   ]:
      guard._pre_tool (_event ("Bash", { "command": command }, tmp_path))

   for value in _emitted (capsys):
      specific = value ["hookSpecificOutput"]
      assert "permissionDecision" not in specific
      assert set (specific) <= { "hookEventName", "additionalContext" }


def test_install_merge_removes_stale_guard_events (tmp_path):
   install = _module ("imp_agent_install", "adapters/install.py")
   settings = tmp_path / "settings.json"
   settings.write_text (json.dumps ({
      "hooks": {
         "SessionStart": [
            { "hooks": [ { "type": "command", "command": "python3 /x/imp/agents/agent_guard.py claude" } ] },
         ],
         "SessionEnd": [
            { "hooks": [ { "type": "command", "command": "python3 /x/imp/agents/agent_guard.py claude" } ] },
         ],
         "PreToolUse": [
            { "hooks": [ { "type": "command", "command": "python3 /x/imp/agents/agent_guard.py claude" } ] },
            { "hooks": [ { "type": "command", "command": "other-tool --check" } ] },
         ],
      },
      "permissions": { "defaultMode": "acceptEdits" },
   }))

   install._merge (settings, "claude")

   value = json.loads (settings.read_text ())
   assert "SessionStart" not in value ["hooks"]
   assert "SessionEnd" not in value ["hooks"]
   groups = value ["hooks"] ["PreToolUse"]
   assert any ("other-tool" in json.dumps (group) for group in groups)
   assert len ([ group for group in groups if "agent_guard.py" in json.dumps (group) ]) == 1
   assert value ["permissions"] == { "defaultMode": "acceptEdits" }


def test_codex_guard_requires_the_advisory_hook_trusted (monkeypatch):
   hooks = [
      {
         "command": "python3 /home/test/.config/imp/agents/agent_guard.py codex",
         "enabled": True,
         "eventName": "preToolUse",
         "trustStatus": "trusted",
      }
   ]
   monkeypatch.setattr (doctor, "_codex_hooks", lambda cwd: hooks)

   assert doctor._codex_guard (Path.cwd ()) == (True, "trusted")

   hooks [0] ["trustStatus"] = "modified"

   assert doctor._codex_guard (Path.cwd ()) == (False, "review-required")


def _claude_settings (events):
   return {
      "hooks": {
         event: [
            {
               "matcher": "*",
               "hooks": [ { "type": "command", "command": "python3 /x/imp/agents/agent_guard.py claude" } ],
            }
         ]
         for event in events
      }
   }


def _install_adapter (home):
   install = home / ".config" / "imp" / "agents"
   install.mkdir (parents=True, exist_ok=True)
   (install / "adapter.json").write_text (json.dumps ({ "version": "1.1.0" }))
   (install / "agent_guard.py").write_text ("guard")
   return install


def test_claude_hook_check_is_structural_and_per_event (tmp_path, monkeypatch):
   monkeypatch.setenv ("HOME", str (tmp_path))
   _install_adapter (tmp_path)
   settings = tmp_path / ".claude" / "settings.json"
   settings.parent.mkdir (parents=True)
   settings.write_text (json.dumps (_claude_settings ([ "PreToolUse" ])))

   report = doctor._agent_report ()
   claude = next (value for value in report ["providers"] if value ["provider"] == "claude")
   assert claude ["hooks"] is True
   assert claude ["events"] == { "PreToolUse": True }

   settings.write_text (json.dumps (_claude_settings ([])))
   report = doctor._agent_report ()
   claude = next (value for value in report ["providers"] if value ["provider"] == "claude")
   assert claude ["hooks"] is False
   assert claude ["events"] == { "PreToolUse": False }


def test_claude_substring_mention_without_registration_is_not_a_hook (tmp_path, monkeypatch):
   monkeypatch.setenv ("HOME", str (tmp_path))
   _install_adapter (tmp_path)
   settings = tmp_path / ".claude" / "settings.json"
   settings.parent.mkdir (parents=True)
   settings.write_text (json.dumps ({ "note": "imp/agents/agent_guard.py" }))

   report = doctor._agent_report ()
   claude = next (value for value in report ["providers"] if value ["provider"] == "claude")

   assert claude ["hooks"] is False


def test_gemini_row_reports_not_configured_without_failing_doctor (tmp_path, monkeypatch):
   monkeypatch.setenv ("HOME", str (tmp_path))
   _install_adapter (tmp_path)
   claude_settings = tmp_path / ".claude" / "settings.json"
   claude_settings.parent.mkdir (parents=True)
   claude_settings.write_text (json.dumps (_claude_settings ([ "PreToolUse" ])))
   codex_settings = tmp_path / ".codex" / "hooks.json"
   codex_settings.parent.mkdir (parents=True)
   codex_settings.write_text ("imp/agents/agent_guard.py")
   monkeypatch.setattr (doctor, "_codex_guard", lambda cwd: (True, "trusted"))

   report = doctor._agent_report ()
   gemini = next (value for value in report ["providers"] if value ["provider"] == "gemini")

   assert gemini ["hook_mechanism"] is False
   assert gemini ["hook_trust"] == "not-configured"
   assert gemini ["effective_enforcement"] == "none"
   assert gemini ["skill"] is False
   assert report ["ok"] is True


def test_guard_drift_reports_modified_deployment (tmp_path):
   install = tmp_path / "agents"
   install.mkdir ()
   packaged = Path (doctor.__file__).resolve ().parents [3] / "adapters" / "agent_guard.py"
   (install / "agent_guard.py").write_bytes (packaged.read_bytes ())
   assert doctor._guard_drift (install) == "in-sync"

   (install / "agent_guard.py").write_text ("tampered")
   assert doctor._guard_drift (install) == "modified"

   (install / "agent_guard.py").unlink ()
   assert doctor._guard_drift (install) == "unknown"
