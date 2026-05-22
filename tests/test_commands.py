import os
from pathlib import Path

import pytest
import typer

from imp import ai, console, git
from imp.commands import branch as branch_cmd
from imp.commands import commit as commit_cmd
from imp.commands import merge as merge_cmd
from imp.commands import push as push_mod
from imp.commands import tag as tag_cmd
from imp.commands import review as review_cmd
from imp.commands import setup as setup_cmd
from tests.conftest import commit_file, git_run, last_commit_subject


class TestCommitCommand:

   def test_commits_with_ai_message (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

      assert last_commit_subject (repo) == "feat: add login"

   def test_commit_all_stages_everything (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add feature")
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      (repo / "new.txt").write_text ("new file\n")

      commit_cmd.commit (all=True, exclude=None, yes=False, push=False, whisper="")

      assert last_commit_subject (repo) == "feat: add feature"

   def test_commit_cancelled (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "No")

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      with pytest.raises (typer.Exit):
         commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

      assert git.commit_count () == 1

   def test_commit_nothing_staged (self, repo, monkeypatch):
      with pytest.raises (typer.Exit):
         commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

   def test_commit_push_calls_do_push (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      pushed = []
      monkeypatch.setattr (push_mod, "do_push", lambda: pushed.append (True))

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      commit_cmd.commit (all=False, exclude=None, yes=False, push=True, whisper="")

      assert len (pushed) == 1

   def test_commit_push_skipped_on_cancel (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "No")

      pushed = []
      monkeypatch.setattr (push_mod, "do_push", lambda: pushed.append (True))

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      with pytest.raises (typer.Exit):
         commit_cmd.commit (all=False, exclude=None, yes=False, push=True, whisper="")

      assert len (pushed) == 0

   def test_commit_no_push_by_default (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add login")
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      pushed = []
      monkeypatch.setattr (push_mod, "do_push", lambda: pushed.append (True))

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

      assert len (pushed) == 0

   def test_commit_retries_on_invalid_ai (self, repo, monkeypatch):
      calls = []

      def mock_fast (prompt):
         calls.append (1)
         if len (calls) == 1:
            return "GARBAGE"
         return "fix: resolve bug"

      monkeypatch.setattr (ai, "fast", mock_fast)
      monkeypatch.setattr (console, "review", lambda text: "Yes")

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      commit_cmd.commit (all=False, exclude=None, yes=False, push=False, whisper="")

      assert last_commit_subject (repo) == "fix: resolve bug"
      assert len (calls) == 2


class TestBranchCommand:

   def test_creates_branch (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat/user-auth")
      monkeypatch.setattr (console, "confirm", lambda msg: True)

      branch_cmd._create ("add user authentication")

      assert git.branch () == "feat/user-auth"

   def test_create_cancelled (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat/user-auth")
      monkeypatch.setattr (console, "confirm", lambda msg: False)

      with pytest.raises (typer.Exit):
         branch_cmd._create ("add user authentication")

      assert git.branch () == "main"

   def test_rejects_invalid_name (self, repo, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt: "invalid branch name!")

      with pytest.raises (typer.Exit):
         branch_cmd._create ("something")


class TestReviewCommand:

   def test_reviews_staged_changes (self, repo, monkeypatch, mock_spin):
      captured = {}

      def mock_smart (prompt, spin=True):
         captured ["prompt"] = prompt
         return "Code looks good. No issues found."

      monkeypatch.setattr (ai, "smart", mock_smart)

      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")

      review_cmd.review (last=0, whisper="")

      assert "prompt" in captured
      assert "changed" in captured ["prompt"]

   def test_reviews_last_n_commits (self, repo, monkeypatch, mock_spin):
      captured = {}

      def mock_smart (prompt, spin=True):
         captured ["prompt"] = prompt
         return "Code looks good. No issues found."

      monkeypatch.setattr (ai, "smart", mock_smart)

      commit_file (repo, "file.txt", "first\n", "first")
      commit_file (repo, "file.txt", "second\n", "second")

      review_cmd.review (last=2, whisper="")

      assert "prompt" in captured
      assert "second" in captured ["prompt"]

   def test_review_no_changes (self, repo):
      with pytest.raises (typer.Exit):
         review_cmd.review (last=0, whisper="")


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


class TestSetupCommand:

   @pytest.fixture
   def bare_dir (self, tmp_path):
      old_cwd = Path.cwd ()
      os.chdir (tmp_path)
      yield tmp_path
      os.chdir (old_cwd)

   def test_initializes_repo_and_remote (self, bare_dir, monkeypatch, mock_spin):
      monkeypatch.setattr (ai, "fast", lambda prompt, spin=True: "node_modules\n.env\n")

      (bare_dir / "package.json").write_text ("{}\n")

      setup_cmd.setup (url="https://github.com/test/repo.git")

      assert (bare_dir / ".git").is_dir ()
      result = git_run (bare_dir, "remote", "get-url", "origin")
      assert result.stdout.strip () == "https://github.com/test/repo.git"
      assert (bare_dir / ".gitignore").exists ()
      contents = (bare_dir / ".gitignore").read_text ()
      assert "node_modules" in contents

   def test_skips_init_if_already_repo (self, repo, monkeypatch, mock_spin):
      monkeypatch.setattr (ai, "fast", lambda prompt, spin=True: ".env\n")

      setup_cmd.setup (url="https://github.com/test/repo.git")

      result = git_run (repo, "remote", "get-url", "origin")
      assert result.stdout.strip () == "https://github.com/test/repo.git"

   def test_merges_existing_gitignore (self, bare_dir, monkeypatch, mock_spin):
      monkeypatch.setattr (ai, "fast", lambda prompt, spin=True: "dist\n")

      (bare_dir / ".gitignore").write_text ("node_modules\n")
      (bare_dir / "index.js").write_text ("//\n")

      setup_cmd.setup (url="https://github.com/test/repo.git")

      contents = (bare_dir / ".gitignore").read_text ()
      assert "node_modules" in contents
      assert "dist" in contents

   def test_no_gitignore_changes_when_none_needed (self, bare_dir, monkeypatch, mock_spin):
      monkeypatch.setattr (ai, "fast", lambda prompt, spin=True: "NONE")

      (bare_dir / "file.txt").write_text ("hello\n")

      setup_cmd.setup (url="https://github.com/test/repo.git")

      assert not (bare_dir / ".gitignore").exists ()


class TestMergeCommand:

   def _branch_with_commit (self, repo, name, path, content, msg):
      git_run (repo, "checkout", "-b", name)
      commit_file (repo, path, content, msg)
      git_run (repo, "checkout", "main")

   def test_clean_merge_creates_merge_commit (self, repo):
      self._branch_with_commit (repo, "feature", "new.txt", "hello\n", "add new")

      merge_cmd.merge (
         source="feature",
         yes=True,
         no_ff=True,
         whisper="",
         favor_ours=False,
         favor_theirs=False,
         auto=False,
      )

      assert (repo / "new.txt").exists ()
      assert last_commit_subject (repo).startswith ("Merge branch 'feature'")

   def test_ff_merge_does_not_create_commit (self, repo):
      before = git.commit_count ()
      self._branch_with_commit (repo, "feature", "new.txt", "hello\n", "add new")

      merge_cmd.merge (
         source="feature",
         yes=True,
         no_ff=False,
         whisper="",
         favor_ours=False,
         favor_theirs=False,
         auto=False,
      )

      assert last_commit_subject (repo) == "add new"
      assert git.commit_count () == before + 1

   def test_rejects_self_merge (self, repo):
      with pytest.raises (typer.Exit):
         merge_cmd.merge (
            source="main",
            yes=True,
            no_ff=True,
            whisper="",
            favor_ours=False,
            favor_theirs=False,
            auto=False,
         )

   def test_rejects_missing_branch (self, repo):
      with pytest.raises (typer.Exit):
         merge_cmd.merge (
            source="ghost",
            yes=True,
            no_ff=True,
            whisper="",
            favor_ours=False,
            favor_theirs=False,
            auto=False,
         )

   def test_rejects_dirty_tree (self, repo):
      self._branch_with_commit (repo, "feature", "new.txt", "hello\n", "add new")
      (repo / "file.txt").write_text ("dirty\n")

      with pytest.raises (typer.Exit):
         merge_cmd.merge (
            source="feature",
            yes=True,
            no_ff=True,
            whisper="",
            favor_ours=False,
            favor_theirs=False,
            auto=False,
         )

   def test_cancelled_aborts (self, repo, monkeypatch):
      self._branch_with_commit (repo, "feature", "new.txt", "hello\n", "add new")
      monkeypatch.setattr (console, "confirm", lambda msg: False)

      with pytest.raises (typer.Exit):
         merge_cmd.merge (
            source="feature",
            yes=False,
            no_ff=True,
            whisper="",
            favor_ours=False,
            favor_theirs=False,
            auto=False,
         )

      assert not (repo / "new.txt").exists ()

   def test_resolves_conflict_via_ai (self, repo, monkeypatch):
      git_run (repo, "checkout", "-b", "feature")
      commit_file (repo, "file.txt", "feature side\n", "feature change")
      git_run (repo, "checkout", "main")
      commit_file (repo, "file.txt", "main side\n", "main change")

      monkeypatch.setattr (ai, "smart", lambda prompt: "resolved content\n")

      merge_cmd.merge (
         source="feature",
         yes=True,
         no_ff=True,
         whisper="",
         favor_ours=False,
         favor_theirs=False,
         auto=True,
      )

      assert (repo / "file.txt").read_text () == "resolved content"
      assert last_commit_subject (repo).startswith ("Merge branch 'feature'")
      assert not git.merge_in_progress ()


class TestTagCommand:

   def _tag_args (self, **overrides):
      defaults = dict (patch=False, minor=False, major=False, yes=True, no_push=True)
      defaults.update (overrides)
      return defaults

   def _seed (self, repo, tag_name=None, message="feat: add thing"):
      """Commit a change so release_scope has something to work with."""
      if tag_name:
         git_run (repo, "tag", tag_name)
      commit_file (repo, "feature.txt", "x\n", message)

   def test_bumps_patch_and_writes_changelog (self, repo):
      self._seed (repo, "v0.1.0", "feat: add login")

      tag_cmd.tag (** self._tag_args (patch=True))

      assert git.tag_exists ("v0.1.1")
      changelog = (repo / "CHANGELOG.md").read_text ()
      assert "## [0.1.1]" in changelog
      assert "Add login" in changelog
      assert last_commit_subject (repo) == "chore: release v0.1.1"

   def test_bumps_minor_resets_patch (self, repo):
      self._seed (repo, "v0.1.5")

      tag_cmd.tag (** self._tag_args (minor=True))

      assert git.tag_exists ("v0.2.0")

   def test_bumps_major_resets_lower (self, repo):
      self._seed (repo, "v1.2.3")

      tag_cmd.tag (** self._tag_args (major=True))

      assert git.tag_exists ("v2.0.0")

   def test_first_tag_from_zero (self, repo):
      tag_cmd.tag (** self._tag_args (patch=True))

      assert git.tag_exists ("v0.0.1")

   def test_uses_highest_stable_tag (self, repo):
      git_run (repo, "tag", "v0.1.0")
      commit_file (repo, "a.txt", "a", "a")
      git_run (repo, "tag", "v0.2.0")
      commit_file (repo, "b.txt", "b", "b")
      git_run (repo, "tag", "v0.1.5")  # lexically lower, but irrelevant

      tag_cmd.tag (** self._tag_args (patch=True))

      assert git.tag_exists ("v0.2.1")

   def test_appends_to_existing_changelog (self, repo):
      (repo / "CHANGELOG.md").write_text (
         "# Changelog\n\n## [0.1.0] - 2024-01-01\n\n### Added\n- Original\n"
      )
      git_run (repo, "add", "CHANGELOG.md")
      git_run (repo, "commit", "-m", "docs: seed changelog")
      self._seed (repo, "v0.1.0", "fix: a bug")

      tag_cmd.tag (** self._tag_args (patch=True))

      content = (repo / "CHANGELOG.md").read_text ()
      assert "## [0.1.1]" in content
      assert "## [0.1.0]" in content
      assert content.index ("[0.1.1]") < content.index ("[0.1.0]")

   def test_rejects_multiple_levels (self, repo):
      with pytest.raises (typer.Exit):
         tag_cmd.tag (** self._tag_args (patch=True, minor=True))

   def test_rejects_existing_tag (self, repo, monkeypatch):
      self._seed (repo, "v0.1.1")
      monkeypatch.setattr (tag_cmd, "current_version", lambda: "0.1.0")

      with pytest.raises (typer.Exit):
         tag_cmd.tag (** self._tag_args (patch=True))

   def test_rejects_dirty_tree (self, repo):
      git_run (repo, "tag", "v0.1.0")
      (repo / "dirty.txt").write_text ("uncommitted\n")

      with pytest.raises (typer.Exit):
         tag_cmd.tag (** self._tag_args (patch=True))

      assert not git.tag_exists ("v0.1.1")

   def test_interactive_choice (self, repo, monkeypatch):
      self._seed (repo, "v0.1.0")
      monkeypatch.setattr (console, "choose", lambda title, opts: "minor")

      tag_cmd.tag (** self._tag_args (yes=True))

      assert git.tag_exists ("v0.2.0")

   def test_cancelled (self, repo, monkeypatch):
      self._seed (repo, "v0.1.0")
      monkeypatch.setattr (console, "confirm", lambda msg: False)

      with pytest.raises (typer.Exit):
         tag_cmd.tag (** self._tag_args (patch=True, yes=False))

      assert not git.tag_exists ("v0.1.1")
      assert not (repo / "CHANGELOG.md").exists ()
