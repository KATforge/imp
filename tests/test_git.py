import subprocess

import pytest
import typer

from imp_git import git
from tests.conftest import commit_file, git_run, last_commit_subject


class TestRequire:

   def test_passes_in_repo (self, repo):
      git.require ()

   def test_fails_outside_repo (self, tmp_path, monkeypatch):
      monkeypatch.chdir (tmp_path)
      with pytest.raises (typer.Exit):
         git.require ()


class TestFetch:

   def test_fails_when_git_fetch_fails (self, repo, monkeypatch):
      error = subprocess.CalledProcessError (1, [ "git", "fetch" ], stderr="offline")
      monkeypatch.setattr (git, "_run", lambda *args, **kwargs: (_ for _ in ()).throw (error))

      with pytest.raises (typer.Exit):
         git.fetch ()


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

   def test_follows_origin_head (self, repo):
      git_run (repo, "update-ref", "refs/remotes/origin/develop", "HEAD")
      git_run (repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
      assert git.base_branch () == "develop"

   def test_falls_back_without_trunk (self, repo):
      git_run (repo, "checkout", "-b", "feature")
      git_run (repo, "branch", "-D", "main")
      assert git.base_branch () == "main"


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

   def test_stable_skips_rc (self, repo):
      git_run (repo, "tag", "v0.1.0")
      commit_file (repo, "f.txt", "x\n", "c")
      git_run (repo, "tag", "v0.2.0-rc.1")
      assert git.highest_tag (stable=True) == "v0.1.0"

   def test_stable_skips_non_semver (self, repo):
      git_run (repo, "tag", "v0.1.0")
      commit_file (repo, "f.txt", "x\n", "c")
      git_run (repo, "tag", "v2024.5.1.3")
      commit_file (repo, "f2.txt", "y\n", "c2")
      git_run (repo, "tag", "v1.2")
      assert git.highest_tag (stable=True) == "v0.1.0"


class TestTagOperations:

   def test_tag_create_and_exists (self, repo):
      assert not git.tag_exists ("v1.0.0")
      git.tag ("v1.0.0")
      assert git.tag_exists ("v1.0.0")

class TestTagWithRef:

   def test_tags_specific_commit (self, repo):
      commit_file (repo, "file.txt", "second\n", "feat: second")
      first = git.capture ("rev-list", "--max-parents=0", "HEAD").strip ()
      git.tag ("v1.0.0", ref=first)
      assert git.tag_exists ("v1.0.0")
      assert git.rev_parse ("v1.0.0") == first


class TestLogOneline:

   def test_returns_commits (self, repo):
      result = git.log_oneline (count=5)
      assert "Initial commit" in result

   def test_empty_range (self, repo):
      git_run (repo, "tag", "v1.0.0")
      result = git.log_oneline (rev_range="v1.0.0..HEAD")
      assert result == ""


class TestCommitAmend:

   def test_amend_flag (self, repo):
      (repo / "file.txt").write_text ("changed\n")
      git_run (repo, "add", ".")
      git.commit ("feat: original", amend=True)
      assert last_commit_subject (repo) == "feat: original"


class TestRepoName:

   def test_returns_name (self, repo):
      name = git.repo_name ()
      assert name


class TestRevParse:

   def test_head (self, repo):
      result = git.rev_parse ("HEAD")
      assert len (result) == 40


class TestStatusShort:

   def test_clean (self, repo):
      assert git.status_short () == ""

   def test_dirty (self, repo):
      (repo / "file.txt").write_text ("dirty\n")
      result = git.status_short ()
      assert "file.txt" in result


class TestDeleteBranch:

   def test_returns_true_on_success (self, repo):
      git_run (repo, "branch", "feat/del")
      assert git.delete_branch ("feat/del") is True

   def test_returns_false_on_failure (self, repo):
      assert git.delete_branch ("nonexistent") is False


class TestIsMerged:

   def test_returns_true_when_ancestor (self, repo):
      git_run (repo, "checkout", "-b", "feat/done")
      commit_file (repo, "done.txt", "done\n", "feat: done")
      git_run (repo, "checkout", "main")
      git_run (repo, "merge", "--no-ff", "feat/done")

      assert git.is_merged ("feat/done", "main") is True

   def test_returns_false_when_not_merged (self, repo):
      git_run (repo, "checkout", "-b", "feat/pending")
      commit_file (repo, "pending.txt", "pending\n", "feat: pending")
      git_run (repo, "checkout", "main")

      assert git.is_merged ("feat/pending", "main") is False
