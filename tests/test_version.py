import pytest

from imp_git.version import (
   bump,
   changelog_from_commits,
   normalize_line,
   sync_manifests,
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

   @pytest.mark.parametrize ("raw", [
      "Generated with Claude Code",
      "Co-Authored-By: Bot <bot@example.com>",
      "actor:codex:release-agent",
   ])
   def test_drops_provenance (self, raw):
      assert normalize_line (raw) == ""


class TestChangelogFromCommits:

   def test_feat (self):
      result = changelog_from_commits ("feat: add login page")
      assert result == "- Added login page"

   def test_fix (self):
      result = changelog_from_commits ("fix: resolve crash on startup")
      assert result == "- Fixed resolve crash on startup"

   def test_other_types (self):
      result = changelog_from_commits ("refactor: simplify auth flow")
      assert result == "- Changed simplify auth flow"

   def test_mixed_keeps_only_the_major_points (self):
      subjects = "feat: add dark mode\nfix: resolve null pointer\nchore: update deps"
      result = changelog_from_commits (subjects)
      assert result.splitlines () == [ "- Added dark mode", "- Fixed resolve null pointer" ]

   def test_an_all_chore_release_still_says_what_happened (self):
      subjects = "chore: update deps\nrefactor: simplify auth flow"
      result = changelog_from_commits (subjects)
      assert result.splitlines () == [ "- Changed deps", "- Changed simplify auth flow" ]

   def test_every_entry_is_one_line (self):
      subjects = "feat: add a very long subject that keeps going and going past any sane width"
      result = changelog_from_commits (subjects)
      assert len (result.splitlines ()) == 1

   def test_non_conventional (self):
      result = changelog_from_commits ("some random commit")
      assert result == "- Changed some random commit"

   def test_a_hex_looking_first_word_survives (self):
      result = changelog_from_commits ("add the search box")
      assert result == "- Changed add the search box"

   def test_an_identifier_keeps_its_case (self):
      result = changelog_from_commits ("fix: SPK-68493 store page text")
      assert result == "- Fixed SPK-68493 store page text"

   def test_an_ordinary_leading_word_is_lowercased (self):
      result = changelog_from_commits ("refactor: Trim verbose comments")
      assert result == "- Changed trim verbose comments"

   def test_an_acronym_survives_the_feature_verb_strip (self):
      result = changelog_from_commits ("feat: add SPK-1234 support for redirects")
      assert result == "- Added SPK-1234 support for redirects"

   def test_empty (self):
      result = changelog_from_commits ("")
      assert result == ""

   def test_scoped_commit (self):
      result = changelog_from_commits ("feat(auth): add oauth support")
      assert result == "- Added oauth support"

PACKAGE_JSON = (
   '{\n   "name": "demo",\n   "version": "1.0.0",\n'
   '   "dependencies": { "left-pad": { "version": "9.9.9" } }\n}\n'
)

PYPROJECT = '[project]\nname = "demo"\nversion = "1.0.0"\n\n[tool.ruff]\ntarget-version = "py310"\n'

PYPROJECT_DYNAMIC = '[project]\nname = "demo"\ndynamic = ["version"]\n\n[tool.hatch.version]\nsource = "vcs"\n'


class TestSyncManifests:

   def test_syncs_all_present (self, tmp_path):
      (tmp_path / "package.json").write_text (PACKAGE_JSON)
      (tmp_path / "cli").mkdir ()
      (tmp_path / "cli" / "pyproject.toml").write_text (PYPROJECT)

      changed = sync_manifests (tmp_path, "3.1.4")

      assert sorted (p.name for p in changed) == [ "package.json", "pyproject.toml" ]
      assert '"version": "3.1.4"' in (tmp_path / "package.json").read_text ()
      assert 'version = "3.1.4"' in (tmp_path / "cli" / "pyproject.toml").read_text ()

   def test_rc_version (self, tmp_path):
      (tmp_path / "package.json").write_text (PACKAGE_JSON)
      sync_manifests (tmp_path, "0.1.0-rc.2")
      assert '"version": "0.1.0-rc.2"' in (tmp_path / "package.json").read_text ()

   def test_empty_repo (self, tmp_path):
      assert sync_manifests (tmp_path, "1.0.0") == []
