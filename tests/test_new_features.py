import json

from typer.testing import CliRunner

from imp import repo as repo_mod
from imp import version
from imp.commands import changelog as changelog_cmd
from imp.main import app


class TestRepoConfig:

   def test_missing_returns_defaults (self, repo):
      assert repo_mod.load () == {}
      assert repo_mod.docs_mode () == "reconcile"
      assert repo_mod.docs_path () == ""
      assert repo_mod.docs_release () is False
      assert repo_mod.changelog_skip () == [ "chore", "merge", "release" ]

   def test_reads_imp (self, repo):
      (repo / ".imp").write_text (json.dumps ({
         "docs:path": "../docs",
         "docs:mode": "additive",
         "docs:release": True,
      }))
      repo_mod.load.cache_clear ()

      assert repo_mod.docs_path () == "../docs"
      assert repo_mod.docs_mode () == "additive"
      assert repo_mod.docs_release () is True

   def test_invalid_json_ignored (self, repo):
      (repo / ".imp").write_text ("{ not json")
      repo_mod.load.cache_clear ()

      assert repo_mod.load () == {}


class TestEntry:

   def test_fast_is_mechanical (self, repo):
      commits = [ { "hash": "x", "subject": "feat: add login", "date": "2025-01-01" } ]

      out = version.entry (commits, fast=True)

      assert "### Added" in out
      assert "Add login" in out

   def test_skip_filters_noise (self, repo):
      commits = [
         { "hash": "x", "subject": "chore: bump dep", "date": "2025-01-01" },
         { "hash": "y", "subject": "feat: new thing", "date": "2025-01-01" },
      ]

      out = version.entry (commits, fast=True).lower ()

      assert "new thing" in out
      assert "bump dep" not in out

   def test_empty_when_all_skipped (self, repo):
      commits = [ { "hash": "x", "subject": "chore: release v1", "date": "2025-01-01" } ]

      assert version.entry (commits, fast=True) == ""


class TestUpsertUnreleased:

   def test_creates_file (self, repo):
      p = repo / "CHANGELOG.md"

      changelog_cmd._upsert_unreleased (p, "### Added\n- Thing")

      content = p.read_text ()
      assert "# Changelog" in content
      assert "## [Unreleased]" in content
      assert "- Thing" in content

   def test_replaces_existing_unreleased_keeps_releases (self, repo):
      p = repo / "CHANGELOG.md"
      p.write_text (
         "# Changelog\n\n"
         "## [Unreleased]\n\n### Added\n- Old\n\n"
         "## [1.0.0] - 2025-01-01\n\n### Added\n- Released\n"
      )

      changelog_cmd._upsert_unreleased (p, "### Added\n- New")

      content = p.read_text ()
      assert "- New" in content
      assert "- Old" not in content
      assert "- Released" in content
      assert content.count ("## [Unreleased]") == 1


class TestNewCommandsRegistered:

   def _help (self, name):
      return CliRunner ().invoke (app, [ name, "--help" ])

   def test_pull (self):
      result = self._help ("pull")
      assert result.exit_code == 0
      assert "--merge" in result.output

   def test_docs (self):
      result = self._help ("docs")
      assert result.exit_code == 0
      assert "--since" in result.output

   def test_init (self):
      result = self._help ("init")
      assert result.exit_code == 0

   def test_setup (self):
      result = self._help ("setup")
      assert result.exit_code == 0

   def test_changelog_rebuild_flag (self):
      result = self._help ("changelog")
      assert result.exit_code == 0
      assert "--rebuild" in result.output
      assert "--fast" in result.output
