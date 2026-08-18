from typing import Any

from imp_git import features, fingerprint, git, identity, integration, plans, repo, state


def _managed () -> list [dict [str, Any]]:
   return [
      feature for feature in features.all ()
      if feature.get ("state") in { "active", "awaiting-merge" }
   ]


def _inventory (actor_id: str) -> tuple [list [dict [str, Any]], list [str]]:
   selected = _managed ()
   blockers = []
   for feature in selected:
      name = str (feature ["name"])
      if feature.get ("worktree_state") != "live":
         blockers.append (f"{name}: worktree is {feature.get ('worktree_state')}")
         continue
      if not git.clean_at (str (feature ["path"])):
         blockers.append (f"{name}: worktree has uncommitted changes")
      holder = features.claimed_by_other (feature, actor_id)
      if holder:
         blockers.append (f"{name}: writer claim is held by {holder}")
   for orphan in features.orphans ():
      label = str (orphan.get ("path") or orphan ["branch"])
      blockers.append (
         f"Unmanaged {orphan ['kind']}: {label}; run imp worktree prune --adopt, then retry"
      )
   return selected, blockers


def _target (into: str) -> str:
   return into or str (repo.get ("done:target", "")) or git.base_branch ()


def _target_blockers (target: str) -> list [str]:
   return [
      f"Target worktree has uncommitted changes: {path}"
      for path in git.ref_worktrees (target)
      if not git.clean_at (path)
   ]


def plan_fleet (
   *,
   actor_id: str,
   into: str = "",
   pr: bool = False,
   strategy: str = "squash",
   persist: bool = True,
) -> dict [str, Any]:
   """Plan every managed feature against one repository target."""

   if strategy not in { "preserve", "squash", "merge" }:
      raise state.StateError (f"Unsupported integration strategy: {strategy}")
   selected, structural_blockers = _inventory (actor_id)
   target = _target (into)
   structural_blockers.extend (_target_blockers (target))
   children = []
   items = []
   blockers = list (structural_blockers)
   check_commands = []
   check_results = []
   start_oid = ""
   final_oid = ""
   if selected and not structural_blockers:
      local_oid, remote_oid, effective_oid = integration.target_state (target)
      start_oid = effective_oid
      final_oid = effective_oid
      for feature in selected:
         resolved = (local_oid, remote_oid, effective_oid) if pr else (final_oid, remote_oid, final_oid)
         try:
            child = integration.plan_done (
               feature,
               actor_id=actor_id,
               into=target,
               pr=pr,
               skip_checks=not pr,
               strategy=strategy,
               resolved_target=resolved,
               allow_configured_push=False,
            )
         except state.StateError as error:
            blockers.append (f"{feature ['name']}: {error}")
            break
         children.append ({
            "branch": feature ["branch"],
            "feature_id": feature ["feature_id"],
            "name": feature ["name"],
            "plan": child,
         })
         action = "pull_request" if pr else "integrate_and_cleanup"
         items.append ({ "action": action, "feature": feature ["name"], "target": target })
         blockers.extend (f"{feature ['name']}: {value}" for value in child.get ("blockers", []))
         if not pr:
            final_oid = str (child ["payload"] ["candidate_oid"])
      if not pr and children and not any ("Integration conflict" in value for value in blockers):
         check_commands = integration.configured_checks ()
         check_results = integration.run_checks (final_oid, check_commands)
         blockers.extend (
            f"Check failed: {value ['name']}" for value in check_results if value ["exit_code"]
         )
   payload = {
      "actor_id": actor_id,
      "check_commands": check_commands,
      "children": children,
      "final_oid": final_oid,
      "mode": "pr" if pr else "local",
      "start_oid": start_oid,
      "strategy": strategy,
      "structural_blockers": structural_blockers,
      "target_ref": target,
   }
   bound = {
      "children": children,
      "final_oid": final_oid,
      "start_oid": start_oid,
      "target_ref": target,
   }
   return plans.build (
      "fleet", git.repo_name (),
      scope={ "repository": git.repo_name () },
      items=items,
      checks=check_results,
      blockers=blockers,
      fingerprint=fingerprint.values (bound),
      payload_schema="imp.fleet-plan.v1",
      payload=payload,
   )


def refresh (plan: dict [str, Any]) -> dict [str, Any]:
   """Refresh review blockers without changing a fleet plan's exact children."""

   if plan.get ("payload_schema") != "imp.fleet-plan.v1":
      raise state.StateError ("Unsupported fleet plan")
   if plan.get ("state") == "applied":
      return plan
   blockers = list (plan ["payload"].get ("structural_blockers", []))
   for child in plan ["payload"].get ("children", []):
      child_plan = child ["plan"]
      if child_plan.get ("state") in { "ready", "applied" }:
         continue
      values = child_plan.get ("blockers", []) or [ f"plan is {child_plan.get ('state')}" ]
      blockers.extend (f"{child ['name']}: {value}" for value in values)
   state_name = "blocked" if blockers else "ready"
   return plans.mark (plan, state_name, blockers=blockers)


def _recovery (plan: dict [str, Any], completed: list [str], error: Exception):
   recovery_id = identity.resource ("recovery", "fleet", str (plan ["label"]), str (len (completed) + 1))
   state.atomic_write (
      state.root () / "recovery" / f"{identity.key (recovery_id)}.json",
      {
         "schema": "imp.recovery.v1",
         "label": str (plan ["label"]),
         "command": "imp fleet",
         "completed": completed,
         "created_at": state.now (),
         "error": str (error),
         "next": "imp fleet",
         "recovery_id": recovery_id,
      },
   )


def apply_fleet (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   """Apply or resume one exact repository fleet plan."""

   current = refresh (plan)
   if current.get ("state") != "ready":
      raise state.StateError ("Fleet plan is blocked")
   payload = current ["payload"]
   completed = []
   receipts = []
   try:
      with state.lock (f"fleet-{identity.slug (str (payload ['target_ref']))}"):
         if payload ["mode"] == "local" and payload ["children"]:
            failed = [
               check for check in integration.run_checks (payload ["final_oid"], payload ["check_commands"])
               if check ["exit_code"]
            ]
            if failed:
               raise state.StateError (f"Fleet check failed: {failed [0]['name']}")
         for child in payload ["children"]:
            child_plan = child ["plan"]
            if child_plan.get ("state") == "applied":
               completed.append (str (child ["feature_id"]))
               continue
            receipts.append (integration.apply_done (child_plan, actor_id))
            completed.append (str (child ["feature_id"]))
         plans.mark (current, "applied", applied_at=state.now ())
   except Exception as error:
      _recovery (current, completed, error)
      raise
   return {
      "completed": completed,
      "mode": payload ["mode"],
      "receipts": receipts,
      "target": payload ["target_ref"],
   }
