import json
import sys

import pytest
import typer
from typer.testing import CliRunner

from imp_git import ai, console, git, runtime
from imp_git import main as main_mod
from imp_git.main import app
from tests.conftest import commit_count, git_run

runner = CliRunner ()


class TestSurface:

   def test_release_preview_names_tag_and_notes (self, repo):
      for index in range (1, 4):
         path = repo / f"change-{index}.txt"
         path.write_text (f"{index}\n")
         git_run (repo, "add", path.name)
         git_run (repo, "commit", "-m", f"feat: add change {index}")

      result = runner.invoke (app, [ "--dry-run", "release", "1.2.3", "--local" ])

      assert result.exit_code == 0
      assert "v1.2.3" in result.output
      for index in range (1, 4):
         assert f"feat: add change {index}" in result.output

   def test_help_contains_only_the_small_native_surface (self):
      result = runner.invoke (app, [ "--help" ])

      assert result.exit_code == 0
      for command in [ "start", "status", "commit", "done", "release", "pr", "worktree" ]:
         assert command in result.output
      removed_commands = [
         "active", "amend", "bisect", "changelog", "context", "guard",
         "cleanup", "config", "fleet", "init", "recover", "resolve", "review", "revert", "ship", "split",
         "tidy", "undo", "use",
      ]
      for removed in removed_commands:
         assert f"│ {removed} " not in result.output
      assert "--actor-id" not in result.output
      assert "only commit calls AI" in result.output
      assert "pass -m to send nothing" in result.output
      assert "all others are deterministic" in result.output

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
         [ "active" ], [ "context" ], [ "guard" ], [ "init", "--bare" ],
         [ "resolve", "--ours" ], [ "split" ], [ "use" ],
      ]
      for args in commands:
         result = runner.invoke (app, args)
         assert result.exit_code == 0

      assert seen == commands

   def test_done_exposes_only_all (self):
      result = runner.invoke (app, [ "done", "--help" ])

      assert result.exit_code == 0
      assert "--approve" not in result.output
      assert "--all" in result.output
      assert "--keep" not in result.output
      assert "--strategy" not in result.output

   def test_release_exposes_semver_options (self):
      result = runner.invoke (app, [ "release", "--help" ])

      assert result.exit_code == 0
      for option in [ "--local", "--major", "--minor", "--patch", "--rc", "--stable" ]:
         assert option in result.output

   def test_pr_exposes_target_branch (self):
      result = runner.invoke (app, [ "pr", "--help" ])

      assert result.exit_code == 0
      assert "--into" in result.output

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
      assert value ["data"] ["message"] == "exploded"
      assert value ["error"] == { "message": "exploded", "type": "RuntimeError" }

   def test_usage_error_emits_versioned_error_envelope (self, monkeypatch, capsys, tmp_path):
      monkeypatch.chdir (tmp_path)
      monkeypatch.setattr (sys, "argv", [ "imp", "--json", "done", "--nope" ])
      monkeypatch.setattr (runtime, "options", runtime.Options ())

      code = main_mod.run ()
      value = json.loads (capsys.readouterr ().out)

      assert code == 2
      assert value ["schema"] == "imp.error.v1"
      assert value ["command"] == "imp done"
      assert value ["ok"] is False
      assert "--nope" in value ["data"] ["message"]

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

      result = runner.invoke (app, [ "--json", "--dry-run", "commit" ])

      assert result.exit_code == 0
      value = json.loads (result.stdout)
      assert value ["schema"] == "imp.commit-plan.v3"
      assert value ["data"] ["plan"] ["state"] == "ready"
      assert commit_count (repo) == 1


   def test_ephemeral_plan_reports_no_identity (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      result = runner.invoke (app, [ "commit", "--dry-run" ])

      assert result.exit_code == 0
      assert "Plan saved" not in result.stdout


   def test_json_fails_closed_without_explicit_approval (self, repo, monkeypatch):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      result = runner.invoke (app, [ "--json", "commit" ])

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

      result = runner.invoke (app, [ "--json", "--dry-run", "commit" ])

      assert result.exit_code == 1
      value = json.loads (result.stdout)
      assert value ["schema"] == "imp.error.v1"
      assert value ["ok"] is False
      assert value ["command"] == "imp commit"
      assert value ["data"] ["message"]


class TestHelpOrdering:

   def _options (self, *args: str) -> list [str]:
      result = runner.invoke (app, [ *args, "--help" ])

      assert result.exit_code == 0
      return [
         value.split () [0]
         for line in result.output.splitlines ()
         if (value := line.strip ("│ ").strip ()).startswith ("--")
      ]

   def test_help_shows_the_workflow_diagrams (self):
      result = runner.invoke (app, [ "--help" ])

      lines = [ line.strip () for line in result.output.splitlines () ]

      assert result.exit_code == 0
      assert "start ─► edit ─► commit ─► done ─► trunk" in lines
      assert "└──────── isolated worktree ────────┘" in lines
      assert "one checkout          a directory of checkouts" in lines

   def test_global_options_are_alphabetical_with_help_last (self):
      options = self._options ()

      assert options [-1] == "--help"
      assert options [:-1] == sorted (options [:-1])

   def test_every_command_orders_its_options_alphabetically (self):
      for command in [ "commit", "done", "start", "release", "pr" ]:
         options = self._options (command)

         assert options [-1] == "--help", command
         assert options [:-1] == sorted (options [:-1]), command

   def test_subcommand_options_are_ordered_too (self):
      options = self._options ("worktree", "remove")

      assert options [-1] == "--help"
      assert options [:-1] == sorted (options [:-1])


class TestPrompts:
   """A machine invocation must fail loudly rather than wait for a person."""

   def test_machine_output_never_prompts (self, capsys):
      runtime.configure (json=True)

      with pytest.raises (typer.Exit):
         console.choose ("Pick one", [ "a", "b" ])

      value = json.loads (capsys.readouterr ().out)
      assert value ["schema"] == "imp.error.v1"
      assert value ["ok"] is False

   def test_refused_input_never_prompts (self):
      runtime.configure (no_input=True)

      with pytest.raises (typer.Exit):
         console.choose ("Pick one", [ "a", "b" ])
