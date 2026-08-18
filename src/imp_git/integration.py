import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from imp_git import conflicts, features, fingerprint, git, identity, plans, repo, state

_HUMAN_APPROVAL_BLOCKERS = {
   "Human review required",
   "Human review or explicit approval required",
}


def _checks () -> list [dict [str, Any]]:
   values = repo.get ("check:commands", []) or []
   if not isinstance (values, list):
      raise state.StateError ("check:commands must be an array")
   checks = []
   for index, value in enumerate (values, start=1):
      if not isinstance (value, dict) or not isinstance (value.get ("run"), list):
         raise state.StateError ("Each check requires a run argv array")
      argv = value ["run"]
      if not argv or not all (isinstance (part, str) and part for part in argv):
         raise state.StateError ("Each check requires a non-empty string argv array")
      checks.append ({ "name": str (value.get ("name") or f"check-{index}"), "run": argv })
   return checks


def configured_checks () -> list [dict [str, Any]]:
   """Return the repository checks bound to an integration candidate."""

   return _checks ()


_STALE_AFTER = 2 * 60 * 60


def _sweep_stale ():
   """Drop temporary worktrees a killed run never got to clean up.

   Cleanup is a finally block, which a SIGKILL skips, so an interrupted
   integration leaves a scratch worktree and its registry entry behind.
   """

   removed = False
   for root in Path (tempfile.gettempdir ()).glob ("imp-*"):
      try:
         if not root.is_dir () or time.time () - root.stat ().st_mtime < _STALE_AFTER:
            continue
         shutil.rmtree (root, ignore_errors=True)
         removed = True
      except OSError:
         continue
   if removed:
      git.prune_worktrees ()


def _temporary_worktree (ref: str, prefix: str) -> tuple [Path, callable]:
   _sweep_stale ()
   root = Path (tempfile.mkdtemp (prefix=f"imp-{prefix}-"))
   path = root / "worktree"
   git.worktree_add_detached (str (path), ref)

   def cleanup ():
      if path.exists ():
         git.worktree_remove (str (path), force=True)
      shutil.rmtree (root, ignore_errors=True)

   return path, cleanup


def run_checks (candidate_oid: str, checks: list [dict [str, Any]] | None = None) -> list [dict [str, Any]]:
   configured = checks if checks is not None else _checks ()
   if not configured:
      return []
   path, cleanup = _temporary_worktree (candidate_oid, "checks")
   results = []
   try:
      for check in configured:
         started = time.monotonic ()
         process = subprocess.run (
            check ["run"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
         )
         output = "\n".join (part.strip () for part in [ process.stdout, process.stderr ] if part.strip ())
         results.append ({
            "duration_ms": round ((time.monotonic () - started) * 1000),
            "exit_code": process.returncode,
            "name": check ["name"],
            "output": output [-8000:],
            "run": check ["run"],
         })
   finally:
      cleanup ()
   return results


def _commits (target_oid: str, feature_oid: str) -> list [str]:
   output = git.capture ("rev-list", "--reverse", f"{target_oid}..{feature_oid}")
   return [line for line in output.splitlines () if line]


def _published (commits: list [str]) -> bool:
   return any (git.published (commit_oid) for commit_oid in commits)


def _rebase_candidate (target_oid: str, feature_oid: str) -> tuple [str, list [dict [str, str]]]:
   before = _commits (git.merge_base (target_oid, feature_oid), feature_oid)
   path, cleanup = _temporary_worktree (feature_oid, "rebase")
   try:
      base_oid = git.merge_base (target_oid, feature_oid)
      result = git.run_at (
         str (path), "rebase", "--onto", target_oid, base_oid, feature_oid,
         check=False, env={ "GIT_SEQUENCE_EDITOR": ":", "GIT_EDITOR": ":" },
      )
      if result.returncode != 0:
         conflicts = git.run_at (
            str (path), "diff", "--name-only", "--diff-filter=U", check=False
         ).stdout.splitlines ()
         raise state.StateError ("Integration conflict" + (f": {', '.join (conflicts)}" if conflicts else ""))
      candidate_oid = git.run_at (str (path), "rev-parse", "HEAD").stdout.strip ()
      after = _commits (target_oid, candidate_oid)
      rewrites = [ { "from": old, "to": new } for old, new in zip (before, after, strict=False) if old != new ]
      return candidate_oid, rewrites
   finally:
      cleanup ()


def _resolved_tree (target_oid: str, feature_oid: str, choice: str) -> tuple [str, list [dict [str, str]]]:
   path, cleanup = _temporary_worktree (target_oid, "resolve")
   try:
      return conflicts.resolve (str (path), target_oid, feature_oid, choice=choice)
   finally:
      cleanup ()


def _candidate (
   feature: dict [str, Any],
   target_oid: str,
   strategy: str,
   resolve: str = "",
) -> tuple [str, list [dict [str, str]], list [dict [str, str]]]:
   feature_oid = git.rev_parse (str (feature ["branch"]))
   if git.is_merged (feature_oid, target_oid):
      return target_oid, []
   commits = _commits (git.merge_base (target_oid, feature_oid), feature_oid)
   if strategy == "preserve" and git.is_merged (target_oid, feature_oid):
      return feature_oid, [], []
   if strategy == "preserve" and not _published (commits):
      rebased, rewrites = _rebase_candidate (target_oid, feature_oid)
      return rebased, rewrites, []

   tree_oid, conflicted = git.merge_tree (target_oid, feature_oid)
   decisions: list [dict [str, str]] = []
   if not tree_oid:
      if not resolve:
         detail = f": {', '.join (conflicted)}" if conflicted else ""
         raise state.StateError (
            f"Integration conflict{detail}; rerun with --resolve ours|theirs|edit|ai"
         )
      tree_oid, decisions = _resolved_tree (target_oid, feature_oid, "" if resolve == "ask" else resolve)
   message = f"Merge {feature ['branch']} into {feature ['target']}"
   if strategy == "squash":
      message = f"feat: integrate {feature ['name']}"
      return git.commit_tree_parents (tree_oid, [ target_oid ], message), [], decisions
   return git.commit_tree_parents (tree_oid, [ target_oid, feature_oid ], message), [], decisions


def _resurrected (base_oid: str, target_oid: str, candidate_oid: str) -> list [str]:
   """Paths the target deleted that this candidate would bring back.

   A branch that predates a deletion still carries the file, and a squash merge
   restores it without reporting a conflict. Landing that silently undoes the
   removal, so it is a blocker rather than a surprise.
   """

   removed = set (git.capture (
      "diff", "--name-only", "--diff-filter=D", base_oid, target_oid,
   ).splitlines ())
   if not removed:
      return []
   present = set (git.capture ("ls-tree", "-r", "--name-only", candidate_oid).splitlines ())

   return sorted (path for path in removed if path and path in present)


def _target_oids (target: str) -> tuple [str, str, str]:
   """Resolve the commit a candidate should be built on.

   Building on the remote tip while local is ahead would discard the local commits,
   so local wins whenever it merely leads the remote, which is the ordinary state
   after integrating and before pushing. Only a genuine divergence is refused.
   """

   local_oid = git.rev_parse (target)
   if not local_oid:
      raise state.StateError (f"Cannot resolve integration target: {target}")
   remote_ref = f"origin/{target}"
   remote_oid = ""
   if git.remote_exists ():
      git.fetch (remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}")
      remote_oid = git.rev_parse (remote_ref)
   if not remote_oid or git.is_merged (remote_oid, local_oid):
      return local_oid, remote_oid, local_oid
   if git.is_merged (local_oid, remote_oid):
      return local_oid, remote_oid, remote_oid

   raise state.StateError (
      f"Local {target} and {remote_ref} have diverged; reconcile them before integrating"
   )


def target_state (target: str) -> tuple [str, str, str]:
   """Resolve local, remote, and effective target objects for one integration train."""

   return _target_oids (target)


def _state_fingerprint (payload: dict [str, Any]) -> str:
   feature = features.find (str (payload ["feature_id"]))
   if not feature:
      return ""
   path = str (feature ["path"])
   value = {
      "candidate_oid": payload ["candidate_oid"],
      "candidate_tree_oid": payload ["candidate_tree_oid"],
      "feature_oid": git.rev_parse (str (feature ["branch"])),
      "status": git.capture ("-C", path, "status", "--porcelain=v1", "-z"),
      "target_oid": payload ["target_oid"],
      "target_ref": payload ["target_ref"],
   }
   return fingerprint.values (value)


def _review_required () -> bool:
   return bool (repo.get ("review:required", False))


def plan_done (
   feature: dict [str, Any],
   *,
   actor_id: str,
   into: str = "",
   keep: bool = False,
   push: bool = False,
   skip_checks: bool = False,
   strategy: str = "",
   resolve: str = "",
   persist: bool = True,
   resolved_target: tuple [str, str, str] | None = None,
   allow_configured_push: bool = True,
) -> dict [str, Any]:
   if feature.get ("state") not in { "active", "awaiting-merge" }:
      raise state.StateError (f"Feature is {feature.get ('state')}")
   if feature.get ("worktree_state") != "live":
      raise state.StateError ("Feature worktree is not live")
   if not git.clean_at (str (feature ["path"])):
      raise state.StateError ("Feature worktree has uncommitted changes")
   chosen_strategy = strategy or str (repo.get ("done:strategy", "preserve"))
   if chosen_strategy not in { "preserve", "squash", "merge" }:
      raise state.StateError (f"Unsupported integration strategy: {chosen_strategy}")
   target = into or str (feature.get ("target") or repo.get ("done:target", "")) or git.base_branch ()
   local_oid, remote_oid, target_oid = resolved_target or _target_oids (target)
   candidate_oid, rewrites, decisions = _candidate (feature, target_oid, chosen_strategy, resolve)
   configured = [] if skip_checks else _checks ()
   check_results = run_checks (candidate_oid, configured)
   blockers = [f"Check failed: {value ['name']}" for value in check_results if value ["exit_code"]]
   revived = _resurrected (
      git.merge_base (target_oid, git.rev_parse (str (feature ["branch"]))), target_oid, candidate_oid,
   )
   if revived:
      blockers.append (
         f"Candidate restores {len (revived)} path(s) {target} deleted: {', '.join (revived [:5])}"
      )
   if _review_required ():
      blockers.append ("Human review or explicit approval required")
   payload = {
      "actor_id": actor_id,
      "candidate_oid": candidate_oid,
      "candidate_tree_oid": git.tree (candidate_oid),
      "check_commands": configured,
      "conflict_decisions": decisions,
      "resurrected": revived,
      "check_results": check_results,
      "feature_id": feature ["feature_id"],
      "feature_oid": git.rev_parse (str (feature ["branch"])),
      "keep": keep,
      "local_target_oid": local_oid,
      "push": push or (allow_configured_push and bool (repo.get ("done:push", False))),
      "remote_target_oid": remote_oid,
      "rewrites": rewrites,
      "skip_checks": skip_checks,
      "state_fingerprint": "",
      "strategy": chosen_strategy,
      "target_oid": target_oid,
      "target_ref": target,
   }
   payload ["state_fingerprint"] = _state_fingerprint (payload)
   items = [
      { "action": "integrate", "candidate_oid": candidate_oid, "target": target },
      *([ { "action": "push", "ref": target } ] if payload ["push"] else []),
      *([ { "action": "cleanup", "feature_id": feature ["feature_id"] } ] if not keep else []),
   ]
   return plans.build (
      "done", str (feature ["name"]),
      scope={ "feature_id": feature ["feature_id"], "repository": git.repo_name () },
      items=items,
      checks=check_results,
      blockers=blockers,
      fingerprint=payload ["state_fingerprint"],
      payload_schema="imp.done-plan.v1",
      payload=payload,
   )


def _approval_path (feature_id: str) -> Path:
   return state.root () / "reviews" / f"{identity.key (feature_id)}.json"


def approval_receipt (feature_id: str) -> dict [str, Any] | None:
   """Return the current human acknowledgement for one feature."""

   path = _approval_path (feature_id)
   if not path.exists ():
      return None
   return state.read (path, "imp.review.v1")


def approval_current (plan: dict [str, Any]) -> bool:
   """Return whether a human acknowledged this exact candidate."""

   payload = plan ["payload"]
   receipt = approval_receipt (str (payload ["feature_id"]))
   return bool (
      receipt
      and receipt.get ("target_oid") == payload ["target_oid"]
      and receipt.get ("candidate_oid") == payload ["candidate_oid"]
      and receipt.get ("state_fingerprint") == _state_fingerprint (payload)
      and str (receipt.get ("acknowledged_by", "")).startswith ("actor:human:")
   )


def _acknowledge (
   plan: dict [str, Any],
   actor_id: str,
   *,
   decision: str,
   files: list [str],
   findings: dict [str, int],
) -> dict [str, Any]:
   if not actor_id.startswith ("actor:human:"):
      raise state.StateError ("Only a human actor can acknowledge a candidate")
   payload = plan ["payload"]
   if _state_fingerprint (payload) != payload ["state_fingerprint"]:
      raise state.StateError ("Integration candidate became stale")
   acknowledged_at = state.now ()
   receipt = {
      "schema": "imp.review.v1",
      "acknowledged_by": actor_id,
      "acknowledged_at": acknowledged_at,
      "candidate_oid": payload ["candidate_oid"],
      "commits": _commits (payload ["target_oid"], payload ["candidate_oid"]),
      "decision": decision,
      "feature_id": payload ["feature_id"],
      "files": files,
      "findings": findings,
      "state_fingerprint": payload ["state_fingerprint"],
      "target_oid": payload ["target_oid"],
      "target_ref": payload ["target_ref"],
   }
   decision_at = "reviewed_at" if decision == "reviewed" else "approved_at"
   receipt [decision_at] = acknowledged_at
   state.atomic_write (_approval_path (str (payload ["feature_id"])), receipt)
   blockers = [value for value in plan.get ("blockers", []) if value not in _HUMAN_APPROVAL_BLOCKERS]
   plans.mark (
      plan,
      "blocked" if blockers else "ready",
      blockers=blockers,
      acknowledged_at=acknowledged_at,
      **{ decision_at: acknowledged_at },
   )
   return receipt


def mark_reviewed (
   plan: dict [str, Any],
   actor_id: str,
   *,
   files: list [str],
   findings: dict [str, int],
) -> dict [str, Any]:
   return _acknowledge (
      plan,
      actor_id,
      decision="reviewed",
      files=files,
      findings=findings,
   )


def waive_review (plan: dict [str, Any]) -> dict [str, Any]:
   """Drop the human-approval blocker from a candidate the caller intends to approve.

   Planning must show what approving would allow without recording it, because the
   caller can still decline at the confirm gate. The receipt is written when the
   integration is applied.
   """

   blockers = [value for value in plan.get ("blockers", []) if value not in _HUMAN_APPROVAL_BLOCKERS]

   return plans.mark (plan, "blocked" if blockers else "ready", blockers=blockers)


def approve (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   """Explicitly approve an exact candidate without recording a review."""

   return _acknowledge (
      plan,
      actor_id,
      decision="approved_without_review",
      files=[],
      findings={ "blocker": 0, "warning": 0, "note": 0 },
   )


def _record_recovery (plan: dict [str, Any], error: Exception, completed: list [str]) -> dict [str, Any]:
   recovery_id = identity.resource ("recovery", "done", str (plan ["label"]), str (len (completed) + 1))
   record = {
      "schema": "imp.recovery.v1",
      "recovery_id": recovery_id,
      "candidate_oid": plan ["payload"].get ("candidate_oid", ""),
      "command": "imp done",
      "completed": completed,
      "label": str (plan ["label"]),
      "target_ref": plan ["payload"].get ("target_ref", ""),
      "error": str (error),
      "next": f"imp done {plan ['label']}",
      "created_at": state.now (),
   }
   state.atomic_write (state.root () / "recovery" / f"{identity.key (recovery_id)}.json", record)
   return record


def _apply_payload (plan: dict [str, Any]) -> tuple [dict [str, Any], dict [str, Any]]:
   if plan.get ("payload_schema") != "imp.done-plan.v1":
      raise state.StateError ("Unsupported integration plan")
   if plan.get ("state") != "ready":
      raise state.StateError (f"Integration plan is {plan.get ('state')}")
   payload = dict (plan ["payload"])
   feature = features.find (str (payload ["feature_id"]))
   if not feature:
      raise state.StateError ("Integration feature is missing")
   return payload, feature


def _direct_receipt (plan: dict [str, Any], payload: dict [str, Any], feature: dict [str, Any]) -> dict [str, Any]:
   return {
      "candidate_oid": payload ["candidate_oid"],
      "feature_id": feature ["feature_id"],
      "mode": "direct",
      "pushed": bool (payload ["push"]),
      "target": payload ["target_ref"],
   }


def _finish_done (plan: dict [str, Any]):
   """Settle the plan as soon as the target moves, before any cleanup can fail.

   Everything after this point is tidying: removing the worktree and the branch.
   Marking the plan applied first means a cleanup failure cannot strand a recovery
   record for work that already landed.
   """

   if plan.get ("state") == "applied":
      return
   plans.mark (plan, "applied", applied_at=state.now ())
   state.clear_recovery (str (plan ["label"]))


def _already_done (payload: dict [str, Any], feature: dict [str, Any], target_oid: str) -> bool:
   return bool (
      feature.get ("state") == "completed"
      and target_oid == payload ["candidate_oid"]
      and not Path (str (feature ["path"])).exists ()
      and not git.ref_exists (str (feature ["branch"]))
   )


def _validate_candidate (
   plan: dict [str, Any],
   payload: dict [str, Any],
   feature: dict [str, Any],
   target_oid: str,
):
   if not git.clean_at (str (feature ["path"])):
      raise state.StateError ("Feature worktree became dirty")
   for path in git.ref_worktrees (str (payload ["target_ref"])):
      if not git.clean_at (path):
         raise state.StateError (f"Target worktree is dirty: {path}")
   if git.rev_parse (str (feature ["branch"])) != payload ["feature_oid"]:
      raise state.StateError ("Feature moved after integration planning")
   if git.remote_exists () and payload ["remote_target_oid"]:
      target = str (payload ["target_ref"])
      git.fetch (remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}")
      current = git.rev_parse (f"origin/{target}")
      if current not in { payload ["remote_target_oid"], payload ["candidate_oid"] }:
         raise state.StateError ("Remote target moved after integration planning")
   if target_oid not in { payload ["local_target_oid"], payload ["candidate_oid"] }:
      raise state.StateError ("Local target moved after integration planning")
   if _state_fingerprint (payload) != payload ["state_fingerprint"]:
      raise state.StateError ("Integration candidate became stale")
   failed = [
      check for check in run_checks (payload ["candidate_oid"], payload ["check_commands"])
      if check ["exit_code"]
   ]
   if failed:
      raise state.StateError (f"Integration check failed: {failed [0]['name']}")
   if _review_required () and not approval_current (plan):
      raise state.StateError (
         f"Current human review or explicit approval required; "
         f"run imp review {feature ['name']} or imp done {feature ['name']} --approve"
      )


def _apply_direct (
   plan: dict [str, Any],
   payload: dict [str, Any],
   feature: dict [str, Any],
   actor_id: str,
   target_oid: str,
   completed: list [str],
) -> dict [str, Any]:
   ref = f"refs/heads/{payload ['target_ref']}"
   if target_oid == payload ["local_target_oid"]:
      git.update_ref_checked (ref, payload ["candidate_oid"], payload ["local_target_oid"])
      for path in git.ref_worktrees (str (payload ["target_ref"])):
         git.reset_at (path, str (payload ["candidate_oid"]))
   completed.append ("integrate")
   if payload ["push"]:
      git.push (ref=str (payload ["target_ref"]))
      completed.append ("push")
   _finish_done (plan)
   features.complete (feature, actor_id, keep=bool (payload ["keep"]))
   completed.append ("cleanup")
   return _direct_receipt (plan, payload, feature)


def apply_done (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   payload, feature = _apply_payload (plan)
   receipt = _direct_receipt (plan, payload, feature)
   completed = []
   try:
      with state.lock (f"done-{identity.slug (str (payload ['target_ref']))}"):
         target_oid = git.rev_parse (str (payload ["target_ref"]))
         if _already_done (payload, feature, target_oid):
            _finish_done (plan)
            return receipt
         _validate_candidate (plan, payload, feature, target_oid)
         data = _apply_direct (plan, payload, feature, actor_id, target_oid, completed)
         _finish_done (plan)

         return data
   except Exception as error:
      _record_recovery (plan, error, completed)
      raise
