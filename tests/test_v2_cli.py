import json
import sys

from typer.testing import CliRunner

from imp_git import ai, git, runtime
from imp_git import main as main_mod
from imp_git.main import app
from tests.conftest import git_run

runner = CliRunner ()


class TestV2Surface:

   def test_help_contains_only_the_small_native_surface (self):
      result = runner.invoke (app, [ "--help" ])

      assert result.exit_code == 0
      for command in [ "start", "use", "status", "commit", "review", "changelog", "guard", "ship", "worktree" ]:
         assert command in result.output
      for removed in [ "amend", "bisect", "fleet", "release", "revert", "tidy", "undo" ]:
         assert f"│ {removed} " not in result.output

   def test_non_native_command_is_forwarded_unchanged (self, monkeypatch):
      seen = []
      monkeypatch.setattr (main_mod.passthrough, "run", lambda args: seen.append (args) or 0)

      result = runner.invoke (app, [ "push", "--force-with-lease" ])

      assert result.exit_code == 0
      assert seen == [ [ "push", "--force-with-lease" ] ]

   def test_bare_optional_values_open_the_native_picker (self):
      assert main_mod._optional_values ([ "commit", "--apply" ]) == [ "commit", "--apply=__pick__" ]
      assert main_mod._optional_values ([ "commit", "--fixup", "HEAD~2" ]) == [ "commit", "--fixup", "HEAD~2" ]

   def test_review_help_hides_internal_marking_option (self):
      result = runner.invoke (app, [ "review", "--help" ])

      assert result.exit_code == 0
      assert "[FEATURE]" in result.output
      assert "--mark-reviewed" not in result.output

   def test_entrypoint_preserves_native_exit_code (self, monkeypatch):
      monkeypatch.setattr (main_mod, "app", lambda standalone_mode: 3)
      monkeypatch.setattr (sys, "argv", [ "imp", "doctor" ])

      assert main_mod.run () == 3


class TestV2Automation:

   def test_json_commit_plan_emits_one_parseable_document (self, repo, monkeypatch):
      runtime.reset ()
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      result = runner.invoke (app, [ "--json", "commit", "--plan" ])

      assert result.exit_code == 0
      value = json.loads (result.stdout)
      assert value ["schema"] == "imp.commit-plan.v2"
      assert value ["data"] ["plan"] ["state"] == "ready"
      assert git.commit_count () == 1

   def test_no_input_fails_closed_without_explicit_approval (self, repo, monkeypatch):
      runtime.reset ()
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      result = runner.invoke (app, [ "--no-input", "commit" ])

      assert result.exit_code == 1
      assert git.commit_count () == 1

   def test_global_yes_applies_an_exact_plan (self, repo, monkeypatch):
      runtime.reset ()
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      monkeypatch.setattr (ai, "fast", lambda prompt: "fix: update value")

      result = runner.invoke (app, [ "--yes", "commit" ])

      assert result.exit_code == 0
      assert git.capture ("log", "-1", "--format=%s").strip () == "fix: update value"

   def test_global_repository_context_works_for_native_json (self, repo, monkeypatch):
      runtime.reset ()
      monkeypatch.chdir (repo.parent)

      result = runner.invoke (app, [ "-C", str (repo), "--json", "status" ])

      assert result.exit_code == 0
      value = json.loads (result.stdout)
      assert value ["data"] ["repository"] == repo.name
      assert value ["data"] ["head_oid"]
