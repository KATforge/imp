import pytest
import typer

from imp import git
from tests.conftest import commit_file, git_run, last_commit_subject


class TestRequire:

   def test_passes_in_repo (self, repo):
      git.require ()

   def test_fails_outside_repo (self, tmp_path, monkeypatch):
      monkeypatch.chdir (tmp_path)
      with pytest.raises (typer.Exit):
         git.require ()


class TestRequireClean:

   def test_passes_when_clean (self, repo):
      git.require_clean ()

   def test_fails_when_dirty (self, repo):
      (repo / "file.txt").write_text ("dirty\n")
      with pytest.raises (typer.Exit):
         git.require_clean ()


class TestDiff:

   def test_empty_when_clean (self, repo):
      assert git.diff (staged=True) == ""

   def test_staged_changes (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", "file.txt")
      assert "changed" in git.diff (staged=True)

   def test_unstaged_changes (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      assert "changed" in git.diff ()


class TestBranch:

   def test_returns_current (self, repo):
      assert git.branch () == "main"


class TestStage:

   def test_stage_all (self, repo):
      (repo / "new.txt").write_text ("new\n")
      git.stage ()
      result = git_run (repo, "diff", "--cached", "--name-only")
      assert "new.txt" in result.stdout


class TestIsClean:

   def test_clean_repo (self, repo):
      assert git.is_clean ()

   def test_dirty_repo (self, repo):
      (repo / "file.txt").write_text ("dirty\n")
      assert not git.is_clean ()


class TestBaseBranch:

   def test_returns_main (self, repo):
      assert git.base_branch () == "main"

   def test_returns_master (self, repo):
      git_run (repo, "branch", "-m", "main", "master")
      assert git.base_branch () == "master"


class TestCommitCount:

   def test_one_commit (self, repo):
      assert git.commit_count () == 1

   def test_two_commits (self, repo):
      commit_file (repo, "file.txt", "changed\n", "second")
      assert git.commit_count () == 2


class TestLastTag:

   def test_no_tags (self, repo):
      assert git.last_tag () == ""

   def test_with_tag (self, repo):
      git_run (repo, "tag", "v1.0.0")
      assert git.last_tag () == "v1.0.0"


class TestHighestTag:

   def test_no_tags (self, repo):
      assert git.highest_tag () == ""

   def test_highest (self, repo):
      git_run (repo, "tag", "v0.1.0")
      commit_file (repo, "file.txt", "v2\n", "second")
      git_run (repo, "tag", "v0.2.0")
      assert git.highest_tag () == "v0.2.0"


class TestTagOperations:

   def test_tag_create_and_exists (self, repo):
      assert not git.tag_exists ("v1.0.0")
      git.tag ("v1.0.0")
      assert git.tag_exists ("v1.0.0")

   def test_tag_delete (self, repo):
      git.tag ("v1.0.0")
      git.tag_delete ("v1.0.0")
      assert not git.tag_exists ("v1.0.0")


class TestTagCommitMap:

   def test_returns_dict (self, repo):
      result = git.tag_commit_map ()
      assert isinstance (result, dict)

   def test_maps_tag_to_commit (self, repo):
      head = git.rev_parse ("HEAD")
      git.tag ("v1.0.0")
      result = git.tag_commit_map ()
      assert result ["v1.0.0"] == head


class TestTagWithRef:

   def test_tags_specific_commit (self, repo):
      commit_file (repo, "file.txt", "second\n", "feat: second")
      first = git.log_full () [0] ["hash"]
      git.tag ("v1.0.0", ref=first)
      assert git.tag_exists ("v1.0.0")
      result = git.tag_commit_map ()
      assert result ["v1.0.0"] == first


class TestLogOneline:

   def test_returns_commits (self, repo):
      result = git.log_oneline (count=5)
      assert "Initial commit" in result

   def test_empty_range (self, repo):
      git_run (repo, "tag", "v1.0.0")
      result = git.log_oneline (rev_range="v1.0.0..HEAD")
      assert result == ""


class TestLogGraph:

   def test_returns_output (self, repo):
      result = git.log_graph (count=5)
      assert "Initial commit" in result


class TestLogFull:

   def test_returns_list (self, repo):
      result = git.log_full ()
      assert isinstance (result, list)
      assert len (result) >= 1

   def test_entry_has_fields (self, repo):
      result = git.log_full ()
      entry = result [0]
      assert "hash" in entry
      assert "subject" in entry
      assert "date" in entry

   def test_respects_since_hash (self, repo):
      commit_file (repo, "file.txt", "second\n", "feat: second")
      first = git.log_full () [0] ["hash"]
      result = git.log_full (since=first)
      hashes = [ e ["hash"] for e in result ]
      assert first not in hashes


class TestLogAfterDate:

   def test_returns_commit_after_date (self, repo):
      result = git.log_after_date ("2000-01-01")
      assert result != ""

   def test_returns_empty_for_future_date (self, repo):
      result = git.log_after_date ("2099-01-01")
      assert result == ""


class TestBranchesLocal:

   def test_lists_branches (self, repo):
      branches = git.branches_local ()
      assert "main" in branches

   def test_multiple_branches (self, repo):
      git.checkout ("feat/test", create=True)
      git.checkout ("main")
      branches = git.branches_local ()
      assert "main" in branches
      assert "feat/test" in branches


class TestBranchesMerged:

   def test_no_merged (self, repo):
      assert git.branches_merged ("main") == []

   def test_merged_branch (self, repo):
      git.checkout ("feat/done", create=True)
      git.checkout ("main")
      merged = git.branches_merged ("main")
      assert "feat/done" in merged


class TestBranchesMergedLstrip:

   def test_branch_starting_with_star_or_space (self, repo):
      """Regression: lstrip('* ') incorrectly strips chars like 's', 'p', 'a', 'c', 'e', '*'."""
      git.checkout ("spaces-test", create=True)
      git.checkout ("main")
      merged = git.branches_merged ("main")
      assert "spaces-test" in merged


class TestCommitAmend:

   def test_amend_flag (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")
      git.commit ("feat: original", amend=True)
      assert last_commit_subject (repo) == "feat: original"


class TestDiffNames:

   def test_unstaged (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      names = git.diff_names ()
      assert "file.txt" in names

   def test_untracked (self, repo):
      (repo / "new.txt").write_text ("new\n")
      names = git.diff_names ()
      assert "new.txt" in names


class TestRepoName:

   def test_returns_name (self, repo):
      name = git.repo_name ()
      assert name


class TestRevParse:

   def test_head (self, repo):
      result = git.rev_parse ("HEAD")
      assert len (result) == 40

   def test_short (self, repo):
      result = git.rev_parse_short ("HEAD")
      assert 4 <= len (result) <= 12


class TestCheckout:

   def test_create_and_switch (self, repo):
      git.checkout ("feat/new", create=True)
      assert git.branch () == "feat/new"

   def test_switch_back (self, repo):
      git.checkout ("feat/new", create=True)
      git.checkout ("main")
      assert git.branch () == "main"


class TestReset:

   def test_soft_reset (self, repo):
      commit_file (repo, "file.txt", "changed\n", "second")
      git.reset ("HEAD~1", soft=True)
      assert git.commit_count () == 1
      assert "changed" in git.diff (staged=True)


class TestResetHard:

   def test_hard_reset (self, repo):
      commit_file (repo, "file.txt", "changed\n", "second")
      git.reset ("HEAD~1", hard=True)
      assert git.commit_count () == 1
      assert (repo / "file.txt").read_text () == "hello\n"


class TestStatusShort:

   def test_clean (self, repo):
      assert git.status_short () == ""

   def test_dirty (self, repo):
      (repo / "file.txt").write_text ("dirty\n")
      result = git.status_short ()
      assert "file.txt" in result


class TestDeleteBranch:

   def test_returns_true_on_success (self, repo):
      git.checkout ("feat/del", create=True)
      git.checkout ("main")
      assert git.delete_branch ("feat/del") is True

   def test_returns_false_on_failure (self, repo):
      assert git.delete_branch ("nonexistent") is False


class TestUnstage:

   def test_unstages_files (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")
      assert git.diff (staged=True) != ""
      git.unstage ()
      assert git.diff (staged=True) == ""


class TestMerge:

   def test_no_ff_creates_merge_commit (self, repo):
      git.checkout ("feat/merge-me", create=True)
      commit_file (repo, "feature.txt", "feature\n", "feat: add feature")
      git.checkout ("main")

      result = git.merge ("feat/merge-me", no_ff=True)

      assert result is True
      assert "Merge branch" in last_commit_subject (repo)

   def test_returns_false_on_conflict (self, repo):
      commit_file (repo, "file.txt", "main version\n", "main change")

      git.checkout ("feat/conflict", create=True)
      git.reset ("HEAD~1", hard=True)
      commit_file (repo, "file.txt", "branch version\n", "branch change")

      git.checkout ("main")

      result = git.merge ("feat/conflict", no_ff=True)

      assert result is False

      git_run (repo, "merge", "--abort")


class TestIsMerged:

   def test_returns_true_when_ancestor (self, repo):
      git.checkout ("feat/done", create=True)
      commit_file (repo, "done.txt", "done\n", "feat: done")
      git.checkout ("main")
      git_run (repo, "merge", "--no-ff", "feat/done")

      assert git.is_merged ("feat/done", "main") is True

   def test_returns_false_when_not_merged (self, repo):
      git.checkout ("feat/pending", create=True)
      commit_file (repo, "pending.txt", "pending\n", "feat: pending")
      git.checkout ("main")

      assert git.is_merged ("feat/pending", "main") is False
