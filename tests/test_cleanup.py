from pathlib import Path

from imp_git import ai, features, git, state
from imp_git.commands import cleanup as cleanup_cmd
from tests.conftest import commit_file


def _feature (name: str, content: str = "") -> dict:
   feature = features.apply_start (features.plan_start (name))
   if content:
      commit_file (Path (feature ["path"]), f"{name}.txt", content, f"feat: add {name}")
   return features.find (name)


class TestCleanup:

   def test_integrate_verdict_lands_the_feature (self, repo, monkeypatch):
      _feature ("good", "good\n")
      monkeypatch.setattr (ai, "verdict", lambda name, age, diff: { "verdict": "integrate", "reason": "Complete." })

      receipt = cleanup_cmd.cleanup ()

      assert receipt ["integrated"] == [ "good" ]
      assert git.capture ("show", "main:good.txt").strip () == "good"
      assert features.find ("good") is None

   def test_discard_verdict_parks_the_tip_in_the_attic (self, repo, monkeypatch):
      _feature ("bad", "bad\n")
      monkeypatch.setattr (ai, "verdict", lambda name, age, diff: { "verdict": "discard", "reason": "Abandoned." })

      receipt = cleanup_cmd.cleanup ()

      assert receipt ["discarded"] [0] ["feature"] == "bad"
      assert receipt ["discarded"] [0] ["attic"] [0].startswith ("refs/imp/attic/bad/")
      assert git.rev_parse (receipt ["discarded"] [0] ["attic"] [0])
      assert features.find ("bad") is None
      assert not git.succeeds ("cat-file", "-e", "main:bad.txt")

   def test_hold_verdict_leaves_the_feature_alone (self, repo, monkeypatch):
      _feature ("unsure", "unsure\n")
      monkeypatch.setattr (ai, "verdict", lambda name, age, diff: { "verdict": "hold", "reason": "Risky." })

      receipt = cleanup_cmd.cleanup ()

      assert receipt ["held"] == [ { "feature": "unsure", "reason": "Risky." } ]
      assert features.find ("unsure") is not None

   def test_empty_feature_is_discarded_without_ai (self, repo, monkeypatch):
      _feature ("empty")

      def explode (name, age, diff):
         raise AssertionError ("AI was called for an empty feature")

      monkeypatch.setattr (ai, "verdict", explode)

      receipt = cleanup_cmd.cleanup ()

      assert receipt ["discarded"] [0] ["feature"] == "empty"

   def test_dirty_work_is_committed_before_judgement_lands_it (self, repo, monkeypatch):
      feature = _feature ("wip", "committed\n")
      (Path (feature ["path"]) / "loose.txt").write_text ("loose\n")
      monkeypatch.setattr (ai, "fast", lambda prompt: "feat: add loose file")
      monkeypatch.setattr (ai, "verdict", lambda name, age, diff: { "verdict": "integrate", "reason": "Fine." })

      receipt = cleanup_cmd.cleanup ()

      assert receipt ["integrated"] == [ "wip" ]
      assert git.capture ("show", "main:loose.txt").strip () == "loose"

   def test_the_verdict_sees_uncommitted_work (self, repo, monkeypatch):
      feature = _feature ("wip", "committed\n")
      (Path (feature ["path"]) / "loose.txt").write_text ("loose\n")
      seen = {}

      def spy (name, age, diff):
         seen ["diff"] = diff
         return { "verdict": "hold", "reason": "Checking." }

      monkeypatch.setattr (ai, "verdict", spy)

      cleanup_cmd.cleanup ()

      assert "loose.txt" in seen ["diff"]

   def test_keep_exempts_a_feature (self, repo, monkeypatch):
      _feature ("precious", "precious\n")

      def explode (name, age, diff):
         raise AssertionError ("AI judged a kept feature")

      monkeypatch.setattr (ai, "verdict", explode)

      receipt = cleanup_cmd.cleanup (keep=[ "precious" ])

      assert receipt ["integrated"] == []
      assert features.find ("precious") is not None

   def test_ai_failure_becomes_a_hold (self, repo, monkeypatch):
      _feature ("odd", "odd\n")

      def broken (name, age, diff):
         raise state.StateError ("AI did not return the requested JSON")

      monkeypatch.setattr (ai, "verdict", broken)

      receipt = cleanup_cmd.cleanup ()

      assert receipt ["held"] [0] ["feature"] == "odd"
      assert features.find ("odd") is not None
