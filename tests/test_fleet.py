import json
from pathlib import Path

from imp_git import features, fleet, git, identity, integration
from imp_git import repo as repo_mod
from tests.conftest import commit_file, git_run

ACTOR = identity.resource ("actor", "human", "anders")


def _feature (repo: Path, name: str, actor_id: str = ACTOR) -> dict:
   path = repo.parent / f"{repo.name}-{name}-fleet"
   plan = features.plan_start (name, actor_id=actor_id, path=str (path))
   value = features.apply_start (plan)
   commit_file (Path (value ["path"]), f"{name}.txt", f"{name}\n", f"feat: add {name}")
   return features.find (str (value ["feature_id"]))


def test_local_fleet_plans_sequential_candidates_and_cleans_every_feature (repo):
   first = _feature (repo, "first")
   second = _feature (repo, "second")

   plan = fleet.plan_fleet (actor_id=ACTOR)
   first_plan = plan ["payload"] ["children"] [0] ["plan"]
   second_plan = plan ["payload"] ["children"] [1] ["plan"]

   assert plan ["state"] == "ready"
   assert first_plan ["payload"] ["target_oid"] == plan ["payload"] ["start_oid"]
   assert second_plan ["payload"] ["target_oid"] == first_plan ["payload"] ["candidate_oid"]

   receipt = fleet.apply_fleet (plan, ACTOR)

   assert receipt ["completed"] == [ first ["feature_id"], second ["feature_id"] ]
   assert git.capture ("show", "main:first.txt").strip () == "first"
   assert git.capture ("show", "main:second.txt").strip () == "second"
   assert not Path (first ["path"]).exists ()
   assert not Path (second ["path"]).exists ()


def test_fleet_blocks_dirty_and_unmanaged_feature_state (repo):
   feature = _feature (repo, "dirty")
   (Path (feature ["path"]) / "uncommitted.txt").write_text ("dirty\n")
   git_run (repo, "branch", "feature/orphan")

   plan = fleet.plan_fleet (actor_id=ACTOR)

   assert plan ["state"] == "blocked"
   assert plan ["payload"] ["children"] == []
   assert any ("uncommitted changes" in value for value in plan ["blockers"])
   assert any ("worktree prune --adopt" in value for value in plan ["blockers"])


def test_agent_fleet_becomes_ready_after_exact_member_review (repo):
   (repo / ".imp").write_text (json.dumps ({ "review:required": True }))
   git_run (repo, "add", ".imp")
   git_run (repo, "commit", "-m", "chore: require review")
   repo_mod.load.cache_clear ()
   agent = identity.resource ("actor", "codex", "session-1")
   feature = _feature (repo, "agent", agent)
   features.release (feature, agent)

   plan = fleet.plan_fleet (actor_id=ACTOR)
   child = plan ["payload"] ["children"] [0] ["plan"]

   assert plan ["state"] == "blocked"
   integration.mark_reviewed (
      child,
      ACTOR,
      files=[ "agent.txt" ],
      findings={ "blocker": 0, "warning": 0, "note": 0 },
   )

   refreshed = fleet.refresh (plan)

   assert refreshed ["state"] == "ready"
   fleet.apply_fleet (refreshed, ACTOR)
   assert git.capture ("show", "main:agent.txt").strip () == "agent"


def test_pr_fleet_pushes_each_branch_and_keeps_worktrees (repo_with_origin, monkeypatch):
   feature = _feature (repo_with_origin, "profile")
   monkeypatch.setattr (integration.gh, "pr_view", lambda _head: {})
   monkeypatch.setattr (
      integration.gh,
      "pr_create",
      lambda _title, _body, _base, _head: "https://github.com/katforge/demo/pull/1",
   )
   plan = fleet.plan_fleet (actor_id=ACTOR, pr=True)

   receipt = fleet.apply_fleet (plan, ACTOR)

   assert receipt ["mode"] == "pr"
   assert features.find (str (feature ["feature_id"])) ["state"] == "awaiting-merge"
   assert Path (feature ["path"]).is_dir ()
   assert git.rev_parse (f"origin/{feature ['branch']}") == git.rev_parse (str (feature ["branch"]))


def test_local_fleet_never_inherits_the_repository_push_default (repo_with_origin, monkeypatch):
   original_get = repo_mod.get
   monkeypatch.setattr (
      repo_mod,
      "get",
      lambda key, default=None: True if key == "done:push" else original_get (key, default),
   )
   _feature (repo_with_origin, "local-only")
   remote_before = git.rev_parse ("origin/master")

   plan = fleet.plan_fleet (actor_id=ACTOR)
   fleet.apply_fleet (plan, ACTOR)

   assert git.rev_parse ("master") != remote_before
   assert git.rev_parse ("origin/master") == remote_before
