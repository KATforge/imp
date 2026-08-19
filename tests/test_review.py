from pathlib import Path

from imp_git import ai, features, runtime
from imp_git.commands import review as review_cmd
from tests.conftest import commit_file, git_run


def _feature (name: str = "checkout") -> dict:
   feature = features.apply_start (features.plan_start (name))
   commit_file (Path (feature ["path"]), f"{name}.txt", f"{name}\n", f"feat: add {name}")
   return features.find (name)


class TestScope:

   def test_reviews_a_feature_against_trunk (self, repo, monkeypatch):
      _feature ()
      seen = {}

      def fake_review (diff):
         seen ["diff"] = diff
         return { "summary": "Adds checkout.", "annotations": [] }

      monkeypatch.setattr (ai, "review_diff", fake_review)

      data = review_cmd.review ("checkout")

      assert "+checkout" in seen ["diff"]
      assert data ["summary"] == "Adds checkout."
      assert data ["scope"].startswith ("feature/checkout")

   def test_reviews_unpushed_trunk_by_default (self, repo_with_origin, monkeypatch):
      git_run (repo_with_origin, "checkout", "master")
      commit_file (repo_with_origin, "landed.txt", "landed\n", "feat: land work")
      monkeypatch.setattr (
         ai, "review_diff",
         lambda diff: { "summary": "Lands work.", "annotations": [
            { "file": "landed.txt", "line": 1, "severity": "info", "note": "New file." },
         ] },
      )

      data = review_cmd.review ()

      assert data ["scope"] == "unpushed master"
      assert data ["commits"]
      assert data ["annotations"] [0] ["file"] == "landed.txt"

   def test_nothing_to_review_when_trunk_is_pushed (self, repo_with_origin, monkeypatch):
      def explode (diff):
         raise AssertionError ("AI was called with nothing to review")

      monkeypatch.setattr (ai, "review_diff", explode)

      data = review_cmd.review ()

      assert data ["annotations"] == []


class TestAsk:

   def test_one_question_gets_one_answer (self, repo, monkeypatch):
      _feature ()
      monkeypatch.setattr (ai, "answer", lambda diff, question: f"Answer to {question}")

      data = review_cmd.review ("checkout", ask="Is this safe?")

      assert data ["answer"] == "Answer to Is this safe?"

   def test_json_emits_a_versioned_envelope (self, repo, monkeypatch, capsys):
      import json

      _feature ()
      runtime.configure (json=True, yes=True)
      monkeypatch.setattr (
         ai, "review_diff", lambda diff: { "summary": "Fine.", "annotations": [] },
      )
      capsys.readouterr ()

      review_cmd.review ("checkout")

      value = json.loads (capsys.readouterr ().out)
      assert value ["schema"] == "imp.review.v1"
      assert value ["data"] ["summary"] == "Fine."


class TestRendering:

   def test_hunks_carry_new_file_line_ranges (self):
      diff = (
         "diff --git a/one.txt b/one.txt\n"
         "--- a/one.txt\n"
         "+++ b/one.txt\n"
         "@@ -1,2 +10,3 @@\n"
         " context\n"
         "+added\n"
         " context\n"
      )

      hunks = review_cmd._hunks (diff)

      assert len (hunks) == 1
      assert hunks [0] ["file"] == "one.txt"
      assert hunks [0] ["start"] == 10
      assert hunks [0] ["end"] == 13
