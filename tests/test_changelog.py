import json

from typer.testing import CliRunner

from imp import ai
from imp.commands.changelog import _build_version_map, _generate_changelog, _infer_versions, _tag_plan
from imp.main import app


class TestBuildVersionMap:

   def test_single_tag (self):
      tags = { "v0.0.1": "aaa" }
      commits = [
         { "hash": "aaa", "subject": "feat: init", "date": "2025-01-01" },
      ]
      result = _build_version_map (tags, commits)
      assert len (result) == 1
      assert result [0] ["version"] == "0.0.1"
      assert result [0] ["date"] == "2025-01-01"

   def test_two_tags (self):
      tags = { "v0.0.1": "bbb", "v0.0.2": "ddd" }
      commits = [
         { "hash": "aaa", "subject": "feat: first", "date": "2025-01-01" },
         { "hash": "bbb", "subject": "chore: release v0.0.1", "date": "2025-01-01" },
         { "hash": "ccc", "subject": "fix: bug", "date": "2025-01-02" },
         { "hash": "ddd", "subject": "chore: release v0.0.2", "date": "2025-01-02" },
      ]
      result = _build_version_map (tags, commits)
      assert len (result) == 2
      assert result [0] ["version"] == "0.0.1"
      assert result [1] ["version"] == "0.0.2"

   def test_commits_after_last_tag_are_unreleased (self):
      tags = { "v0.0.1": "aaa" }
      commits = [
         { "hash": "aaa", "subject": "feat: init", "date": "2025-01-01" },
         { "hash": "bbb", "subject": "feat: new", "date": "2025-01-02" },
      ]
      result = _build_version_map (tags, commits)
      unreleased = [ v for v in result if v ["version"] == "Unreleased" ]
      assert len (unreleased) == 1

   def test_no_tags_returns_single_unreleased (self):
      tags = {}
      commits = [
         { "hash": "aaa", "subject": "feat: init", "date": "2025-01-01" },
         { "hash": "bbb", "subject": "feat: new", "date": "2025-01-02" },
      ]
      result = _build_version_map (tags, commits)
      assert len (result) == 1
      assert result [0] ["version"] == "Unreleased"


class TestInferVersions:

   def test_parses_ai_response (self, monkeypatch):
      response = json.dumps ([
         { "version": "0.0.1", "commits": [ "feat: init", "fix: bug" ] },
         { "version": "0.0.2", "commits": [ "feat: new feature" ] },
      ])
      monkeypatch.setattr (ai, "fast", lambda prompt, spin=True: response)
      commits = [
         { "hash": "aaa", "subject": "feat: init", "date": "2025-01-01" },
         { "hash": "bbb", "subject": "fix: bug", "date": "2025-01-01" },
         { "hash": "ccc", "subject": "feat: new feature", "date": "2025-01-02" },
      ]
      result = _infer_versions (commits)
      assert len (result) == 2
      assert result [0] ["version"] == "0.0.1"
      assert len (result [0] ["commits"]) == 2

   def test_fallback_on_bad_json (self, monkeypatch):
      monkeypatch.setattr (ai, "fast", lambda prompt, spin=True: "not valid json")
      commits = [
         { "hash": "aaa", "subject": "feat: init", "date": "2025-01-01" },
      ]
      result = _infer_versions (commits)
      assert len (result) == 1
      assert result [0] ["version"] == "Unreleased"


class TestGenerateChangelog:

   def test_single_version (self):
      versions = [ {
         "version": "0.0.1",
         "date": "2025-01-01",
         "commits": [
            { "hash": "aaa", "subject": "feat: add login", "date": "2025-01-01" },
         ],
      } ]
      result = _generate_changelog (versions)
      assert "# Changelog" in result
      assert "## [0.0.1] - 2025-01-01" in result
      assert "### Added" in result
      assert "Add login" in result

   def test_unreleased_section (self):
      versions = [ {
         "version": "Unreleased",
         "date": "2025-01-02",
         "commits": [
            { "hash": "aaa", "subject": "feat: wip", "date": "2025-01-02" },
         ],
      } ]
      result = _generate_changelog (versions)
      assert "## [Unreleased]" in result

   def test_multiple_versions_ordered (self):
      versions = [
         {
            "version": "0.0.1",
            "date": "2025-01-01",
            "commits": [
               { "hash": "aaa", "subject": "feat: first", "date": "2025-01-01" },
            ],
         },
         {
            "version": "0.0.2",
            "date": "2025-01-02",
            "commits": [
               { "hash": "bbb", "subject": "fix: second", "date": "2025-01-02" },
            ],
         },
      ]
      result = _generate_changelog (versions)
      # Newest version should appear first in the file
      pos_1 = result.index ("0.0.2")
      pos_2 = result.index ("0.0.1")
      assert pos_1 < pos_2


class TestTagPlan:

   def test_no_missing_tags (self):
      versions = [ {
         "version": "0.0.1",
         "date": "2025-01-01",
         "commits": [
            { "hash": "aaa", "subject": "feat: init", "date": "2025-01-01" },
         ],
      } ]
      existing_tags = { "v0.0.1": "aaa" }
      result = _tag_plan (versions, existing_tags)
      assert len (result) == 0

   def test_missing_tag (self):
      versions = [ {
         "version": "0.0.1",
         "date": "2025-01-01",
         "commits": [
            { "hash": "aaa", "subject": "feat: init", "date": "2025-01-01" },
         ],
      } ]
      existing_tags = {}
      result = _tag_plan (versions, existing_tags)
      assert len (result) == 1
      assert result [0] ["tag"] == "v0.0.1"
      assert result [0] ["hash"] == "aaa"

   def test_mismatched_tag (self):
      versions = [ {
         "version": "0.0.1",
         "date": "2025-01-01",
         "commits": [
            { "hash": "aaa", "subject": "feat: init", "date": "2025-01-01" },
         ],
      } ]
      existing_tags = { "v0.0.1": "bbb" }
      result = _tag_plan (versions, existing_tags)
      assert len (result) == 1
      assert result [0] ["action"] == "move"

   def test_unreleased_skipped (self):
      versions = [ {
         "version": "Unreleased",
         "date": "2025-01-01",
         "commits": [
            { "hash": "aaa", "subject": "feat: wip", "date": "2025-01-01" },
         ],
      } ]
      result = _tag_plan (versions, {})
      assert len (result) == 0


class TestChangelogCommand:

   def test_help (self):
      runner = CliRunner ()
      result = runner.invoke (app, [ "changelog", "--help" ])
      assert result.exit_code == 0
      assert "--since" in result.output
      assert "--apply" in result.output
