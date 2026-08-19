import pytest
import typer

from imp_git import ai, console, git, runtime
from imp_git.commands import commit as commit_cmd
from tests.conftest import commit_count, commit_file, git_run, last_commit_subject


class TestCommitCommand:

   def test_commits_with_ai_message (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "confirm", lambda text: True)

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      commit_cmd.commit ()

      assert last_commit_subject (repo) == "feat: add login"

   def test_commit_all_stages_everything (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add feature")
      monkeypatch.setattr (console, "confirm", lambda text: True)

      (repo / "new.txt").write_text ("new file\n")

      commit_cmd.commit ()

      assert last_commit_subject (repo) == "feat: add feature"

   def test_commit_cancelled (self, repo, monkeypatch):
      runtime.configure ()
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "confirm", lambda text: False)

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      with pytest.raises (typer.Exit):
         commit_cmd.commit ()

      assert commit_count (repo) == 1

   def test_commit_nothing_staged (self, repo, monkeypatch):
      with pytest.raises (typer.Exit):
         commit_cmd.commit ()

   def test_commit_retries_on_invalid_ai (self, repo, monkeypatch):
      calls = []

      def mock_fast (prompt):
         calls.append (1)
         if len (calls) == 1:
            return "GARBAGE"
         return "fix: resolve bug"

      monkeypatch.setattr (ai, "fast", mock_fast)
      monkeypatch.setattr (console, "confirm", lambda text: True)

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      commit_cmd.commit ()

      assert last_commit_subject (repo) == "fix: resolve bug"
      assert len (calls) == 2

class TestStatusParsing:

   def test_path_not_truncated (self, repo):
      """Regression: line[2:].lstrip(' ') must not strip path characters."""

      (repo / "settings.py").write_text ("CONFIG = True\n")

      raw = git.status_short ()
      for line in raw.splitlines ():
         if len (line) < 4:
            continue
         path = line [2:].lstrip (" ")
         assert path == "settings.py", f"Path was truncated to '{path}'"

   def test_modified_path_preserved (self, repo):
      """Paths starting with space-like chars survive lstrip(' ')."""

      (repo / "  spaced.txt").write_text ("edge case\n")

      raw = git.status_short ()
      found = False
      for line in raw.splitlines ():
         if len (line) < 4:
            continue
         path = line [2:].lstrip (" ")
         if "spaced" in path:
            found = True
      assert found, "File with leading spaces not found in status"


class TestPullRequest:

   def test_pr_pushes_the_branch_and_creates_one (self, repo_with_origin, monkeypatch):
      from imp_git.commands import pr as pr_cmd

      git_run (repo_with_origin, "checkout", "-b", "feature/widget")
      commit_file (repo_with_origin, "widget.txt", "widget\n", "feat: add the widget")
      pushed, created = [], []
      monkeypatch.setattr (pr_cmd.gh, "available", lambda: True)
      monkeypatch.setattr (pr_cmd.gh, "pr_view", lambda head: {})
      monkeypatch.setattr (
         pr_cmd.gh, "pr_create",
         lambda title, body, base, head: created.append ((base, head)) or "https://example.test/1",
      )
      monkeypatch.setattr (pr_cmd.git, "push", lambda **kwargs: pushed.append (kwargs))

      data = pr_cmd.pr ()

      assert pushed == [ { "set_upstream": True, "target": "feature/widget" } ]
      assert created == [ ("master", "feature/widget") ]
      assert data ["url"] == "https://example.test/1"

   def test_pr_pushes_an_existing_one_without_duplicating (self, repo_with_origin, monkeypatch):
      from imp_git.commands import pr as pr_cmd

      git_run (repo_with_origin, "checkout", "-b", "feature/widget")
      commit_file (repo_with_origin, "widget.txt", "widget\n", "feat: add the widget")
      monkeypatch.setattr (pr_cmd.gh, "available", lambda: True)
      monkeypatch.setattr (pr_cmd.gh, "pr_view", lambda head: { "url": "https://example.test/7" })
      monkeypatch.setattr (
         pr_cmd.gh, "pr_update", lambda *_args: None,
      )
      monkeypatch.setattr (
         pr_cmd.gh, "pr_create", lambda *_args: pytest.fail ("existing pull request was duplicated"),
      )
      monkeypatch.setattr (pr_cmd.git, "push", lambda **kwargs: None)

      data = pr_cmd.pr ()

      assert data ["url"] == "https://example.test/7"

   def test_pr_targets_an_explicit_branch (self, repo_with_origin, monkeypatch):
      from imp_git.commands import pr as pr_cmd

      git_run (repo_with_origin, "branch", "develop", "master")
      git_run (repo_with_origin, "checkout", "-b", "feature/widget", "develop")
      commit_file (repo_with_origin, "widget.txt", "widget\n", "feat: add the widget")
      created = []
      monkeypatch.setattr (pr_cmd.gh, "available", lambda: True)
      monkeypatch.setattr (pr_cmd.gh, "pr_view", lambda head: {})
      monkeypatch.setattr (
         pr_cmd.gh, "pr_create",
         lambda title, body, base, head: created.append ((base, head)) or "https://example.test/1",
      )
      monkeypatch.setattr (pr_cmd.git, "push", lambda **kwargs: None)

      data = pr_cmd.pr (into="develop")

      assert created == [ ("develop", "feature/widget") ]
      assert data ["base"] == "develop"

   def test_pr_refuses_to_target_its_own_branch (self, repo_with_origin, monkeypatch):
      from imp_git.commands import pr as pr_cmd

      git_run (repo_with_origin, "checkout", "master")
      monkeypatch.setattr (pr_cmd.gh, "available", lambda: True)

      with pytest.raises (typer.Exit):
         pr_cmd.pr ()

class TestStandingWarning:

   def test_done_warns_when_run_inside_the_worktree_it_removes (self, repo_with_origin, tmp_path, monkeypatch):
      import os
      from pathlib import Path

      from imp_git import features
      from imp_git.commands import done as done_cmd
      from imp_git.commands import start as start_cmd

      start_cmd.start (name="standing")
      feature = features.find ("standing")
      previous = Path.cwd ()
      os.chdir (feature ["path"])
      try:
         warnings = done_cmd._standing_here ()
      finally:
         os.chdir (previous)

      assert any (str (feature ["path"]) in text for text in warnings)

   def test_done_stays_quiet_from_the_repository_root (self, repo_with_origin, tmp_path, monkeypatch):
      from imp_git.commands import done as done_cmd
      from imp_git.commands import start as start_cmd

      start_cmd.start (name="standing")

      assert done_cmd._standing_here () == []
