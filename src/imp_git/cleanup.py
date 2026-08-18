from pathlib import Path
from typing import Any

from imp_git import features, fingerprint, git, plans, repo, state

OPEN = { "active", "awaiting-merge" }
TERMINAL = { "completed", "removed" }


def _feature_snapshot (feature: dict [str, Any]) -> dict [str, Any]:
   path = str (feature ["path"])
   live = feature.get ("worktree_state") == "live"

   return {
      "base_oid": feature.get ("base:oid", ""),
      "branch": feature ["branch"],
      "branch_oid": git.rev_parse (str (feature ["branch"])),
      "claim": feature.get ("claim"),
      "feature_id": feature ["feature_id"],
      "name": feature ["name"],
      "path": path,
      "path_exists": Path (path).exists (),
      "state": feature.get ("state", ""),
      "status": git.run_at (path, "status", "--porcelain=v1", check=False).stdout if live else "",
      "target": feature.get ("target", ""),
      "target_oid": git.rev_parse (str (feature.get ("target", ""))),
      "worktree_state": feature.get ("worktree_state", ""),
   }


def _orphan_snapshot (orphan: dict [str, Any], target: str) -> dict [str, Any]:
   path = str (orphan.get ("path", ""))

   return {
      **orphan,
      "branch_oid": git.rev_parse (str (orphan.get ("branch", ""))),
      "status": git.run_at (path, "status", "--porcelain=v1", check=False).stdout if path else "",
      "target": target,
      "target_oid": git.rev_parse (target),
   }


def _snapshot () -> dict [str, Any]:
   target = str (repo.get ("done:target", "")) or git.base_branch ()
   stale = [
      name for name in [ "active.json", "contexts", "plans" ]
      if (state.root () / name).exists ()
   ]

   return {
      "features": [ _feature_snapshot (feature) for feature in features.all () ],
      "orphans": [ _orphan_snapshot (orphan, target) for orphan in features.orphans () ],
      "recoveries": state.recoveries (),
      "stale": stale,
      "worktrees": git.worktrees (),
   }


def _remaining_feature (feature: dict [str, Any], reason: str, next_command: str = "") -> dict [str, Any]:
   return {
      "kind": "feature",
      "name": feature ["name"],
      "path": feature ["path"],
      "reason": reason,
      "next": next_command,
   }


def _feature_action (action: str, feature: dict [str, Any]) -> dict [str, Any]:
   return {
      "action": action,
      "branch": feature ["branch"],
      "branch_oid": feature ["branch_oid"],
      "feature_id": feature ["feature_id"],
      "name": feature ["name"],
      "path": feature ["path"],
      "state": feature ["state"],
   }


def _feature_actions (feature: dict [str, Any]) -> tuple [list [dict [str, Any]], list [dict [str, Any]]]:
   actions: list [dict [str, Any]] = []
   remaining: list [dict [str, Any]] = []
   state_name = str (feature ["state"])
   branch = str (feature ["branch"])
   target = str (feature ["target"])
   claim = feature.get ("claim")
   expired = bool (claim and features.claim_expired (feature))
   claimed = bool (claim and not expired)
   live = feature ["worktree_state"] == "live"
   branch_exists = bool (feature ["branch_oid"])
   merged = branch_exists and bool (target) and git.is_merged (branch, target)

   if claimed:
      holder = str (claim.get ("held_by", "unknown"))
      return actions, [ _remaining_feature (feature, f"claimed by {holder}") ]

   if state_name in TERMINAL:
      if live and feature ["status"]:
         return actions, [ _remaining_feature (feature, "terminal worktree is dirty") ]
      if feature ["worktree_state"] == "branch-mismatch":
         return actions, [ _remaining_feature (feature, "worktree branch does not match its record") ]
      if live or branch_exists:
         actions.append (_feature_action ("discard_closed_feature", feature))
      else:
         actions.append (_feature_action ("purge_feature", feature))
      return actions, remaining

   if state_name not in OPEN:
      return actions, [ _remaining_feature (feature, f"unknown feature state: {state_name}") ]
   if feature ["worktree_state"] == "branch-mismatch":
      return actions, [ _remaining_feature (feature, "worktree branch does not match its record") ]
   if not branch_exists:
      if expired:
         actions.append (_feature_action ("release_expired_claim", feature))
      return actions, [ _remaining_feature (feature, "feature branch is missing") ]
   if not live:
      if merged:
         actions.append (_feature_action ("settle_feature", feature))
         return actions, remaining
      if expired:
         actions.append (_feature_action ("release_expired_claim", feature))
      if not feature ["path_exists"]:
         actions.append (_feature_action ("restore_feature", feature))
         return actions, remaining
      return actions, [ _remaining_feature (feature, "feature worktree path is occupied") ]
   if feature ["status"]:
      if expired:
         actions.append (_feature_action ("release_expired_claim", feature))
      return actions, [ _remaining_feature (feature, "uncommitted changes", f"imp review {feature ['name']}") ]
   if merged:
      actions.append (_feature_action ("settle_feature", feature))
      return actions, remaining
   if expired:
      actions.append (_feature_action ("release_expired_claim", feature))
   _tree, conflicts = git.merge_tree (target, branch)
   if conflicts:
      reason = f"integration conflicts: {', '.join (conflicts [:3])}"
      next_command = f"imp done {feature ['name']} --resolve ask"
      return actions, [ _remaining_feature (feature, reason, next_command) ]
   return actions, [ _remaining_feature (feature, "unmerged commits", f"imp done {feature ['name']}") ]


def _orphan_actions (orphan: dict [str, Any]) -> tuple [list [dict [str, Any]], list [dict [str, Any]]]:
   branch = str (orphan ["branch"])
   target = str (orphan ["target"])
   label = str (orphan ["path"] or branch)
   if orphan ["status"]:
      remaining = {
         "kind": "orphan",
         "name": label,
         "reason": "uncommitted changes",
         "next": "imp worktree prune --adopt",
      }
      return [], [remaining]
   if branch and orphan ["branch_oid"] and git.is_merged (branch, target):
      action = {
         "action": "discard_orphan",
         "branch": branch,
         "branch_oid": orphan ["branch_oid"],
         "path": orphan ["path"],
         "target": target,
      }
      return [action], []

   return [], [{ "kind": "orphan", "name": label, "reason": "unmerged commits", "next": "imp worktree prune --adopt" }]


def plan_cleanup () -> dict [str, Any]:
   git.require ()
   snapshot = _snapshot ()
   actions: list [dict [str, Any]] = []
   remaining: list [dict [str, Any]] = []
   settling = set ()

   if snapshot ["stale"]:
      actions.append ({ "action": "tidy_state", "paths": snapshot ["stale"] })
   if any ("prunable" in worktree for worktree in snapshot ["worktrees"]):
      actions.append ({ "action": "prune_worktrees" })
   for feature in snapshot ["features"]:
      feature_actions, feature_remaining = _feature_actions (feature)
      actions.extend (feature_actions)
      remaining.extend (feature_remaining)
      if any (
         action ["action"] in { "discard_closed_feature", "settle_feature", "purge_feature" }
         for action in feature_actions
      ):
         settling.add (feature ["name"])
   for recovery in snapshot ["recoveries"]:
      if recovery.get ("label") in settling:
         actions.append ({
            "action": "clear_recovery",
            "recovery_id": recovery ["recovery_id"],
            "label": recovery.get ("label", ""),
         })
         continue
      remaining.append ({
         "kind": "recovery",
         "name": recovery.get ("label", recovery ["recovery_id"]),
         "reason": recovery.get ("error", "interrupted operation"),
         "next": recovery.get ("next", ""),
      })
   for orphan in snapshot ["orphans"]:
      orphan_actions, orphan_remaining = _orphan_actions (orphan)
      actions.extend (orphan_actions)
      remaining.extend (orphan_remaining)

   return plans.build (
      "cleanup",
      git.repo_name (),
      scope={ "repository": git.repo_name () },
      items=actions,
      fingerprint=fingerprint.values (snapshot),
      payload_schema="imp.cleanup-plan.v1",
      payload={ "remaining": remaining },
   )


def _apply_action (action: dict [str, Any], actor_id: str):
   name = str (action ["action"])
   if name == "tidy_state":
      state.tidy ()
      return
   if name == "prune_worktrees":
      git.worktree_prune ()
      return
   if name == "clear_recovery":
      state.discard_recovery (str (action ["recovery_id"]))
      return
   if name == "discard_orphan":
      features.discard (action, str (action ["target"]), str (action ["branch_oid"]))
      return
   feature = features.find (str (action ["feature_id"]))
   if not feature:
      raise state.StateError (f"Cleanup feature disappeared: {action ['feature_id']}")
   if name == "release_expired_claim":
      features.drop_expired_claim (feature)
      return
   if name == "restore_feature":
      features.restore (feature)
      return
   if name in { "discard_closed_feature", "settle_feature" }:
      features.complete (feature, actor_id, branch_oid=str (action ["branch_oid"]))
      current = features.find (str (action ["feature_id"]))
      if current:
         features.purge (current)
      return
   if name == "purge_feature":
      features.purge (feature)
      return
   raise state.StateError (f"Unsupported cleanup action: {name}")


def apply_cleanup (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   if plan.get ("state") != "ready" or plan.get ("payload_schema") != "imp.cleanup-plan.v1":
      raise state.StateError ("Unsupported cleanup plan")
   with state.lock ("cleanup"):
      current = plan_cleanup ()
      if current ["fingerprint"] != plan.get ("fingerprint"):
         plans.mark (plan, "stale", stale_at=state.now ())
         raise state.StateError ("Cleanup plan is stale")
      for action in plan ["items"]:
         _apply_action (action, actor_id)
   after = plan_cleanup ()
   plans.mark (plan, "applied", applied_at=state.now ())

   return {
      "applied": plan ["items"],
      "clean": not after ["items"] and not after ["payload"] ["remaining"],
      "remaining": after ["payload"] ["remaining"],
   }
