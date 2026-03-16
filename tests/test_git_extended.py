import subprocess

import pytest
import typer

from imp import git


class TestRequireClean:

   def test_passes_when_clean (self, repo):
      git.require_clean ()

   def test_fails_when_dirty (self, repo):
      (repo / "file.txt").write_text ("dirty\n")
      with pytest.raises (typer.Exit):
         git.require_clean ()


class TestCommitCount:

   def test_one_commit (self, repo):
      assert git.commit_count () == 1

   def test_two_commits (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
      subprocess.run (
         [ "git", "commit", "-m", "second" ],
         cwd=repo, check=True, capture_output=True,
      )
      assert git.commit_count () == 2


class TestLastTag:

   def test_no_tags (self, repo):
      assert git.last_tag () == ""

   def test_with_tag (self, repo):
      subprocess.run ([ "git", "tag", "v1.0.0" ], cwd=repo, check=True)
      assert git.last_tag () == "v1.0.0"


class TestHighestTag:

   def test_no_tags (self, repo):
      assert git.highest_tag () == ""

   def test_highest (self, repo):
      subprocess.run ([ "git", "tag", "v0.1.0" ], cwd=repo, check=True)
      (repo / "file.txt").write_text ("v2\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
      subprocess.run (
         [ "git", "commit", "-m", "second" ],
         cwd=repo, check=True, capture_output=True,
      )
      subprocess.run ([ "git", "tag", "v0.2.0" ], cwd=repo, check=True)
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


class TestLogOneline:

   def test_returns_commits (self, repo):
      result = git.log_oneline (count=5)
      assert "Initial commit" in result

   def test_empty_range (self, repo):
      subprocess.run ([ "git", "tag", "v1.0.0" ], cwd=repo, check=True)
      result = git.log_oneline (rev_range="v1.0.0..HEAD")
      assert result == ""


class TestLogGraph:

   def test_returns_output (self, repo):
      result = git.log_graph (count=5)
      assert "Initial commit" in result


class TestBranchesLocal:

   def test_lists_branches (self, repo):
      branches = git.branches_local ()
      assert "main" in branches

   def test_multiple_branches (self, repo):
      subprocess.run (
         [ "git", "checkout", "-b", "feat/test" ],
         cwd=repo, check=True, capture_output=True,
      )
      subprocess.run (
         [ "git", "checkout", "main" ],
         cwd=repo, check=True, capture_output=True,
      )
      branches = git.branches_local ()
      assert "main" in branches
      assert "feat/test" in branches


class TestBranchesMerged:

   def test_no_merged (self, repo):
      assert git.branches_merged ("main") == []

   def test_merged_branch (self, repo):
      subprocess.run (
         [ "git", "checkout", "-b", "feat/done" ],
         cwd=repo, check=True, capture_output=True,
      )
      subprocess.run (
         [ "git", "checkout", "main" ],
         cwd=repo, check=True, capture_output=True,
      )
      merged = git.branches_merged ("main")
      assert "feat/done" in merged


class TestCommitAmend:

   def test_amend_flag (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
      git.commit ("feat: original", amend=True)
      result = subprocess.run (
         [ "git", "log", "-1", "--format=%s" ],
         cwd=repo, capture_output=True, text=True,
      )
      assert result.stdout.strip () == "feat: original"


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
      assert name  # should be the tmp dir name


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
      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
      subprocess.run (
         [ "git", "commit", "-m", "second" ],
         cwd=repo, check=True, capture_output=True,
      )
      git.reset ("HEAD~1", soft=True)
      assert git.commit_count () == 1
      assert "changed" in git.diff (staged=True)


class TestStatusShort:

   def test_clean (self, repo):
      assert git.status_short () == ""

   def test_dirty (self, repo):
      (repo / "file.txt").write_text ("dirty\n")
      result = git.status_short ()
      assert "file.txt" in result


class TestDeleteBranch:

   def test_returns_true_on_success (self, repo):
      subprocess.run (
         [ "git", "checkout", "-b", "feat/del" ],
         cwd=repo, check=True, capture_output=True,
      )
      subprocess.run (
         [ "git", "checkout", "main" ],
         cwd=repo, check=True, capture_output=True,
      )
      assert git.delete_branch ("feat/del") is True

   def test_returns_false_on_failure (self, repo):
      assert git.delete_branch ("nonexistent") is False


class TestResetHard:

   def test_hard_reset (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
      subprocess.run (
         [ "git", "commit", "-m", "second" ],
         cwd=repo, check=True, capture_output=True,
      )
      git.reset ("HEAD~1", hard=True)
      assert git.commit_count () == 1
      assert (repo / "file.txt").read_text () == "hello\n"


class TestUnstage:

   def test_unstages_files (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      subprocess.run ([ "git", "add", "." ], cwd=repo, check=True)
      assert git.diff (staged=True) != ""
      git.unstage ()
      assert git.diff (staged=True) == ""


class TestBranchesMergedLstrip:

   def test_branch_starting_with_star_or_space (self, repo):
      """Regression: lstrip('* ') incorrectly strips chars like 's', 'p', 'a', 'c', 'e', '*'."""
      subprocess.run (
         [ "git", "checkout", "-b", "spaces-test" ],
         cwd=repo, check=True, capture_output=True,
      )
      subprocess.run (
         [ "git", "checkout", "main" ],
         cwd=repo, check=True, capture_output=True,
      )
      merged = git.branches_merged ("main")
      assert "spaces-test" in merged
