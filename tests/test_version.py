import pytest

from imp.version import (
   bump,
   changelog_from_commits,
   normalize,
   normalize_line,
   read_manifest_version,
   sync_manifests,
   tidy_changelog,
   write_package_version,
   write_pyproject_version,
)


class TestBump:

   @pytest.mark.parametrize ("current, level, expected", [
      ("1.2.3", "patch", "1.2.4"),
      ("1.2.3", "minor", "1.3.0"),
      ("1.2.3", "major", "2.0.0"),
      ("0.0.0", "patch", "0.0.1"),
      ("1.2.3", "5.0.0", "5.0.0"),
      ("not-a-version", "patch", "patch"),
      ("99.99.99", "patch", "99.99.100"),
      ("2.5.8", "major", "3.0.0"),
      ("2.5.8", "minor", "2.6.0"),
   ])
   def test_bump (self, current, level, expected):
      assert bump (current, level) == expected


class TestNormalizeLine:

   @pytest.mark.parametrize ("raw, expected", [
      ("- add oauth login", "Add oauth login"),
      ("add oauth login.", "Add oauth login"),
      ("feat(auth): add oauth login", "Add oauth login"),
      ("Add oauth login (see AuthController.php)", "Add oauth login"),
      ("Add oauth login so that users can sign in with Google", "Add oauth login"),
      ("Add oauth login, so users can sign in", "Add oauth login"),
      ("Add oauth login - users can now sign in", "Add oauth login"),
      ("Add oauth login which replaces the old flow", "Add oauth login"),
      ("Pipe prompts via stdin instead of shell arguments", "Pipe prompts via stdin"),
      ("Add oauth login. It replaces the legacy token flow.", "Add oauth login"),
      ("Add   oauth\tlogin", "Add oauth login"),
      ("Fix crash on empty config", "Fix crash on empty config"),
      ("- ", ""),
      ("", ""),
   ])
   def test_normalize_line (self, raw, expected):
      assert normalize_line (raw) == expected

   def test_trims_at_comma_when_over_the_cap (self):
      raw = "Add oauth login, refresh tokens, session revocation and audit logging"
      assert normalize_line (raw) == "Add oauth login"

   def test_keeps_a_short_line_with_a_comma (self):
      assert normalize_line ("Add oauth login, fix logout") == "Add oauth login, fix logout"

   def test_cuts_at_a_mid_line_colon (self):
      raw = "Add `--fast` flag on ship: skips the AI split entirely"
      assert normalize_line (raw) == "Add `--fast` flag on ship"

   def test_keeps_a_colon_with_no_clause_before_it (self):
      assert normalize_line ("Fix crash: null config") == "Fix crash: null config"

   def test_strips_a_changelog_label (self):
      assert normalize_line ("Changed: pipe prompts via stdin") == "Pipe prompts via stdin"

   def test_never_truncates_mid_phrase (self):
      raw = "Speed up changelog generation dramatically without external network dependencies"
      assert normalize_line (raw) == raw


class TestNormalize:

   def test_squeezes_every_bullet (self):
      entry = (
         "### Added\n"
         "- Added a new OAuth login flow (AuthController.php) so users can sign in\n"
         "\n"
         "### Fixed\n"
         "- fix: resolve the crash on empty config.\n"
      )
      assert normalize (entry) == (
         "### Added\n"
         "- Added a new OAuth login flow\n"
         "\n"
         "### Fixed\n"
         "- Resolve the crash on empty config"
      )

   def test_drops_stray_prose (self):
      entry = "Here is the changelog:\n\n### Added\n- Add oauth login"
      assert normalize (entry) == "### Added\n- Add oauth login"

   def test_drops_duplicates_the_squeeze_creates (self):
      entry = "### Added\n- Add oauth login (initial)\n- Add oauth login (polish)"
      assert normalize (entry) == "### Added\n- Add oauth login"

   def test_drops_a_heading_left_empty (self):
      entry = "### Added\n- Add oauth login\n\n### Fixed\n"
      assert normalize (entry) == "### Added\n- Add oauth login"

   def test_empty (self):
      assert normalize ("") == ""


CHANGELOG_MESSY = """\
# Changelog

All notable changes to this project will be documented in this file.

## [0.0.2] - 2026-07-01

### Added
- Added: a new OAuth login flow (AuthController.php) so users can sign in.

### Fixed

## [Unreleased]

## [0.0.1] - 2026-06-01

### Changed
- Sync
"""

CHANGELOG_TIDY = """\
# Changelog

All notable changes to this project will be documented in this file.

## [0.0.2] - 2026-07-01

### Added
- A new OAuth login flow

## [0.0.1] - 2026-06-01

### Changed
- Sync
"""


class TestTidyChangelog:

   def test_tidies_a_messy_file (self):
      assert tidy_changelog (CHANGELOG_MESSY) == CHANGELOG_TIDY

   def test_is_idempotent (self):
      assert tidy_changelog (CHANGELOG_TIDY) == CHANGELOG_TIDY

   def test_keeps_a_released_version_with_nothing_left (self):
      text = "# Changelog\n\n## [0.0.1] - 2026-06-01\n"
      assert tidy_changelog (text) == text

   def test_keeps_an_unreleased_section_that_has_bullets (self):
      text = "# Changelog\n\n## [Unreleased]\n\n### Added\n- Add oauth login\n"
      assert tidy_changelog (text) == text


class TestChangelogFromCommits:

   def test_feat (self):
      result = changelog_from_commits ("feat: add login page")
      assert "### Added" in result
      assert "Add login page" in result

   def test_fix (self):
      result = changelog_from_commits ("fix: resolve crash on startup")
      assert "### Fixed" in result
      assert "Resolve crash on startup" in result

   def test_other_types (self):
      result = changelog_from_commits ("refactor: simplify auth flow")
      assert "### Changed" in result
      assert "Simplify auth flow" in result

   def test_mixed (self):
      subjects = "feat: add dark mode\nfix: resolve null pointer\nchore: update deps"
      result = changelog_from_commits (subjects)
      assert "### Added" in result
      assert "### Fixed" in result
      assert "### Changed" in result

   def test_non_conventional (self):
      result = changelog_from_commits ("some random commit")
      assert "### Changed" in result
      assert "Some random commit" in result

   def test_strips_hash_prefix (self):
      result = changelog_from_commits ("abc1234 feat: add feature")
      assert "### Added" in result
      assert "Add feature" in result

   def test_empty (self):
      result = changelog_from_commits ("")
      assert result == ""

   def test_scoped_commit (self):
      result = changelog_from_commits ("feat(auth): add oauth support")
      assert "### Added" in result
      assert "Add oauth support" in result

PACKAGE_JSON = '{\n   "name": "demo",\n   "version": "1.0.0",\n   "dependencies": { "left-pad": { "version": "9.9.9" } }\n}\n'

PYPROJECT = '[project]\nname = "demo"\nversion = "1.0.0"\n\n[tool.ruff]\ntarget-version = "py310"\n'

PYPROJECT_DYNAMIC = '[project]\nname = "demo"\ndynamic = ["version"]\n\n[tool.hatch.version]\nsource = "vcs"\n'


class TestWritePackageVersion:

   def test_rewrites_top_level_only (self, tmp_path):
      path = tmp_path / "package.json"
      path.write_text (PACKAGE_JSON)

      assert write_package_version (path, "2.0.0")
      text = path.read_text ()
      assert '"version": "2.0.0"' in text
      assert '"version": "9.9.9"' in text

   def test_missing_file (self, tmp_path):
      assert not write_package_version (tmp_path / "package.json", "2.0.0")

   def test_no_version_field (self, tmp_path):
      path = tmp_path / "package.json"
      path.write_text ('{ "name": "demo" }\n')
      assert not write_package_version (path, "2.0.0")

   def test_same_version_no_op (self, tmp_path):
      path = tmp_path / "package.json"
      path.write_text (PACKAGE_JSON)
      assert not write_package_version (path, "1.0.0")


class TestWritePyprojectVersion:

   def test_rewrites_project_version (self, tmp_path):
      path = tmp_path / "pyproject.toml"
      path.write_text (PYPROJECT)

      assert write_pyproject_version (path, "0.0.12")
      text = path.read_text ()
      assert 'version = "0.0.12"' in text
      assert 'target-version = "py310"' in text

   def test_dynamic_version_no_op (self, tmp_path):
      path = tmp_path / "pyproject.toml"
      path.write_text (PYPROJECT_DYNAMIC)
      assert not write_pyproject_version (path, "0.0.12")


class TestReadManifestVersion:

   def test_package_json (self, tmp_path):
      path = tmp_path / "package.json"
      path.write_text (PACKAGE_JSON)
      assert read_manifest_version (path) == "1.0.0"

   def test_pyproject (self, tmp_path):
      path = tmp_path / "pyproject.toml"
      path.write_text (PYPROJECT)
      assert read_manifest_version (path) == "1.0.0"

   def test_absent (self, tmp_path):
      assert read_manifest_version (tmp_path / "package.json") is None
      path = tmp_path / "pyproject.toml"
      path.write_text (PYPROJECT_DYNAMIC)
      assert read_manifest_version (path) is None


class TestSyncManifests:

   def test_syncs_all_present (self, tmp_path):
      (tmp_path / "package.json").write_text (PACKAGE_JSON)
      (tmp_path / "cli").mkdir ()
      (tmp_path / "cli" / "pyproject.toml").write_text (PYPROJECT)

      changed = sync_manifests (tmp_path, "3.1.4")

      assert sorted (p.name for p in changed) == [ "package.json", "pyproject.toml" ]
      assert read_manifest_version (tmp_path / "package.json") == "3.1.4"
      assert read_manifest_version (tmp_path / "cli" / "pyproject.toml") == "3.1.4"

   def test_rc_version (self, tmp_path):
      (tmp_path / "package.json").write_text (PACKAGE_JSON)
      sync_manifests (tmp_path, "0.1.0-rc.2")
      assert read_manifest_version (tmp_path / "package.json") == "0.1.0-rc.2"

   def test_empty_repo (self, tmp_path):
      assert sync_manifests (tmp_path, "1.0.0") == []
