from imp.version import bump, changelog_from_commits


class TestBump:

   def test_patch (self):
      assert bump ("1.2.3", "patch") == "1.2.4"

   def test_minor (self):
      assert bump ("1.2.3", "minor") == "1.3.0"

   def test_major (self):
      assert bump ("1.2.3", "major") == "2.0.0"

   def test_zero (self):
      assert bump ("0.0.0", "patch") == "0.0.1"

   def test_custom_passthrough (self):
      assert bump ("1.2.3", "5.0.0") == "5.0.0"

   def test_invalid_version (self):
      assert bump ("not-a-version", "patch") == "patch"

   def test_large_numbers (self):
      assert bump ("99.99.99", "patch") == "99.99.100"

   def test_major_resets (self):
      assert bump ("2.5.8", "major") == "3.0.0"

   def test_minor_resets_patch (self):
      assert bump ("2.5.8", "minor") == "2.6.0"


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
