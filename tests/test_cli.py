import json
import sys

from typer.testing import CliRunner

from imp_git import ai, git, runtime
from imp_git import main as main_mod
from imp_git.main import app
from tests.conftest import commit_count, git_run

runner = CliRunner ()


class TestSurface:

   def test_help_contains_only_the_small_native_surface (self):
      result = runner.invoke (app, [ "--help" ])

      assert result.exit_code == 0
      for command in [ "start", "use", "status", "commit", "review", "ship", "worktree" ]:
         assert command in result.output
      removed_commands = [
         "amend", "bisect", "changelog", "context", "fleet", "guard",
         "init", "release", "resolve", "revert", "split", "tidy", "undo",
      ]
      for removed in removed_commands:
         assert f"│ {removed} " not in result.output

   def test_worktree_has_no_duplicate_start_or_claim_commands (self):
      result = runner.invoke (app, [ "worktree", "--help" ])

      assert result.exit_code == 0
      assert "│ add " not in result.output
      assert "│ renew " not in result.output

   def test_non_native_command_is_forwarded_unchanged (self, monkeypatch):
      seen = []
      monkeypatch.setattr (main_mod.passthrough, "run", lambda args: seen.append (args) or 0)

      result = runner.invoke (app, [ "push", "--force-with-lease" ])

      assert result.exit_code == 0
      assert seen == [ [ "push", "--force-with-lease" ] ]

   def test_removed_native_commands_return_to_git_passthrough (self, monkeypatch):
      seen = []
      monkeypatch.setattr (main_mod.passthrough, "run", lambda args: seen.append (args) or 0)

      commands = [
         [ "context" ], [ "guard" ], [ "init", "--bare" ],
         [ "resolve", "--ours" ], [ "split" ],
      ]
      for args in commands:
         result = runner.invoke (app, args)
         assert result.exit_code == 0

      assert seen == commands

   def test_bare_optional_values_open_the_native_picker (self):
      assert main_mod._optional_values ([ "commit", "--apply" ]) == [ "commit", "--apply=__pick__" ]
      assert main_mod._optional_values ([ "commit", "--fixup", "HEAD~2" ]) == [ "commit", "--fixup", "HEAD~2" ]

   def test_review_help_hides_internal_marking_option (self):
      result = runner.invoke (app, [ "review", "--help" ])

      assert result.exit_code == 0
      assert "[FEATURE]" in result.output
      assert "--fix" in result.output
      assert "--mark-reviewed" not in result.output

   def test_ship_exposes_prerelease_without_legacy_release_flags (self):
      result = runner.invoke (app, [ "ship", "--help" ])

      assert result.exit_code == 0
      assert "--prerelease" in result.output
      assert "--stable" not in result.output
      assert "--squash" not in result.output

   def test_entrypoint_preserves_native_exit_code (self, monkeypatch):
      monkeypatch.setattr (main_mod, "app", lambda standalone_mode: 3)
      monkeypatch.setattr (sys, "argv", [ "imp", "doctor" ])

      assert main_mod.run () == 3


class TestErrorBoundary:

   def _boom (self, standalone_mode):
      raise RuntimeError ("exploded")

   def test_uncaught_exception_emits_versioned_error_envelope (self, monkeypatch, capsys):
      monkeypatch.setattr (main_mod, "app", self._boom)
      monkeypatch.setattr (sys, "argv", [ "imp", "--json", "status" ])
      monkeypatch.delenv ("IMP_DEBUG", raising=False)

      code = main_mod.run ()
      value = json.loads (capsys.readouterr ().out)

      assert code == 1
      assert value ["schema"] == "imp.error.v1"
      assert value ["command"] == "imp status"
      assert value ["ok"] is False
      assert value ["error"] == { "message": "exploded", "type": "RuntimeError" }

   def test_uncaught_exception_prints_concise_line_without_json (self, monkeypatch, capsys):
      monkeypatch.setattr (main_mod, "app", self._boom)
      monkeypatch.setattr (sys, "argv", [ "imp", "status" ])
      monkeypatch.delenv ("IMP_DEBUG", raising=False)
      monkeypatch.setattr (runtime, "options", runtime.Options ())

      code = main_mod.run ()
      captured = capsys.readouterr ()

      assert code == 1
      assert "exploded" in captured.out
      assert "Traceback" not in captured.out + captured.err

   def test_debug_variable_prints_the_raw_traceback (self, monkeypatch, capsys):
      monkeypatch.setattr (main_mod, "app", self._boom)
      monkeypatch.setattr (sys, "argv", [ "imp", "status" ])
      monkeypatch.setenv ("IMP_DEBUG", "1")
      monkeypatch.setattr (runtime, "options", runtime.Options ())

      code = main_mod.run ()

      assert code == 1
      assert "Traceback" in capsys.readouterr ().err


class TestAutomation:

   def test_json_commit_plan_emits_one_parseable_document (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      result = runner.invoke (app, [ "--json", "commit", "--plan" ])

      assert result.exit_code == 0
      value = json.loads (result.stdout)
      assert value ["schema"] == "imp.commit-plan.v2"
      assert value ["data"] ["plan"] ["state"] == "ready"
      assert commit_count (repo) == 1

   def test_no_input_fails_closed_without_explicit_approval (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      result = runner.invoke (app, [ "--no-input", "commit" ])

      assert result.exit_code == 1
      assert commit_count (repo) == 1

   def test_global_yes_applies_an_exact_plan (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      result = runner.invoke (app, [ "--yes", "commit" ])

      assert result.exit_code == 0
      assert git.capture ("log", "-1", "--format=%s").strip () == "fix: update value"

   def test_global_repository_context_works_for_native_json (self, repo, monkeypatch):
      monkeypatch.chdir (repo.parent)

      result = runner.invoke (app, [ "-C", str (repo), "--json", "status" ])

      assert result.exit_code == 0
      value = json.loads (result.stdout)
      assert value ["data"] ["repository"] == repo.name
      assert value ["data"] ["head_oid"]

   def test_json_failure_emits_one_error_envelope (self, tmp_path, monkeypatch):
      monkeypatch.chdir (tmp_path)

      result = runner.invoke (app, [ "--json", "commit", "--plan" ])

      assert result.exit_code == 1
      value = json.loads (result.stdout)
      assert value ["schema"] == "imp.error.v1"
      assert value ["ok"] is False
      assert value ["command"] == "imp commit"
      assert value ["data"] ["message"]
