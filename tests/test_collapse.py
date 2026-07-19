import pytest
import typer

from imp import git, version
from imp.commands.collapse import _default_floor, _victims, collapse
from tests.conftest import git_run


class TestBaseTuple:

   def test_plain (self):
      assert version.base_tuple ("2.3.1") == (2, 3, 1)

   def test_v_prefix (self):
      assert version.base_tuple ("v2.3.1") == (2, 3, 1)

   def test_rc_suffix_ignored (self):
      assert version.base_tuple ("v2.3.3-rc.1") == (2, 3, 3)

   def test_non_semver (self):
      assert version.base_tuple ("nightly") is None


class TestVictims:

   @pytest.fixture (autouse=True)
   def _tags (self, repo):
      for t in [ "v2.0.0", "v2.1.0", "v2.3.1", "v2.3.2", "v2.3.2-rc.1", "v2.3.3-rc.1", "nightly" ]:
         git_run (repo, "tag", t)

   def test_above_floor_only (self):
      got = _victims ((2, 0, 0), "v2.0.1")
      assert set (got) == { "v2.1.0", "v2.3.1", "v2.3.2", "v2.3.2-rc.1", "v2.3.3-rc.1" }

   def test_keeps_floor_and_below (self):
      assert "v2.0.0" not in _victims ((2, 0, 0), "v2.0.1")

   def test_ignores_non_semver (self):
      assert "nightly" not in _victims ((2, 0, 0), "v2.0.1")

   def test_never_targets_new_tag (self):
      git_run (str (git.repo_root ()), "tag", "v2.4.0")
      assert "v2.4.0" not in _victims ((2, 0, 0), "v2.4.0")


class TestDefaultFloor:

   def test_highest_stable_below (self, repo):
      for t in [ "v2.0.0", "v2.1.0", "v2.2.0" ]:
         git_run (repo, "tag", t)
      # Collapsing into 2.4.0 keeps the newest stable below it.
      assert _default_floor ("2.4.0") == "2.2.0"

   def test_empty_on_renumber_down (self, repo):
      for t in [ "v2.3.1", "v2.3.2" ]:
         git_run (repo, "tag", t)
      # 2.0.1 is below every stable tag — no safe default, --since required.
      assert _default_floor ("2.0.1") == ""


class TestConsolidateChangelog:

   FILE = (
      "# Changelog\n\n"
      "All notable changes to this project will be documented in this file.\n\n"
      "## [2.3.2] - 2026-07-18\n\n### Fixed\n- Tooltip flicker\n\n"
      "## [2.3.1] - 2026-07-18\n\n### Added\n- Quest cards\n\n### Fixed\n- Bad image paths\n\n"
      "## [2.1.0] - 2026-07-13\n\n### Added\n- Spawn maps\n\n"
      "## [2.0.0] - 2026-06-17\n\n### Added\n- The v2 database\n"
   )

   def _run (self):
      return version.consolidate_changelog (self.FILE, (2, 0, 0), "2.0.1", "2026-07-18")

   def test_single_new_section (self):
      out = self._run ()
      assert out.count ("## [2.0.1]") == 1
      for gone in [ "## [2.3.2]", "## [2.3.1]", "## [2.1.0]" ]:
         assert gone not in out

   def test_keeps_floor_and_below (self):
      assert "## [2.0.0]" in self._run ()

   def test_merges_subsections (self):
      out = self._run ()
      body = out.split ("## [2.0.1]") [1].split ("## [2.0.0]") [0]
      # Every collapsed bullet survives, grouped under merged subsections.
      for bullet in [ "Tooltip flicker", "Quest cards", "Bad image paths", "Spawn maps" ]:
         assert bullet in body
      assert body.count ("### Added") == 1
      assert body.count ("### Fixed") == 1

   def test_noop_when_nothing_above_floor (self):
      out = version.consolidate_changelog (self.FILE, (9, 0, 0), "9.0.1", "2026-07-18")
      assert out == self.FILE

   def test_preamble_preserved (self):
      assert self._run ().startswith ("# Changelog\n")


class TestCollapseIntegration:

   def test_renumber_down_local (self, repo, mock_spin):
      for t in [ "v2.1.0", "v2.3.1", "v2.3.2", "v2.3.3-rc.1" ]:
         git_run (repo, "tag", t)

      collapse ("2.0.1", since="2.0.0", yes=True, no_push=True)

      remaining = set (git.tags ())
      assert remaining == { "v2.0.1" }
      assert git.tag_exists ("v2.0.1")

   def test_keeps_floor_tag (self, repo, mock_spin):
      for t in [ "v2.0.0", "v2.3.2" ]:
         git_run (repo, "tag", t)

      collapse ("2.0.1", since="2.0.0", yes=True, no_push=True)

      assert git.tag_exists ("v2.0.0")
      assert git.tag_exists ("v2.0.1")
      assert not git.tag_exists ("v2.3.2")

   def test_refuses_existing_target (self, repo, mock_spin):
      git_run (repo, "tag", "v2.3.2")
      git_run (repo, "tag", "v2.0.1")

      with pytest.raises (typer.Exit):
         collapse ("2.0.1", since="2.0.0", yes=True, no_push=True)
