import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from imp_git import features, fingerprint, gh, git, identity, plans, repo, state, validate


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


def _temporary_worktree (ref: str, prefix: str) -> tuple [Path, callable]:
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


def _candidate (feature: dict [str, Any], target_oid: str, strategy: str) -> tuple [str, list [dict [str, str]]]:
   feature_oid = git.rev_parse (str (feature ["branch"]))
   commits = _commits (git.merge_base (target_oid, feature_oid), feature_oid)
   if strategy == "preserve" and git.is_merged (target_oid, feature_oid):
      return feature_oid, []
   if strategy == "preserve" and not _published (commits):
      return _rebase_candidate (target_oid, feature_oid)

   tree_oid, conflicts = git.merge_tree (target_oid, feature_oid)
   if not tree_oid:
      detail = f": {', '.join (conflicts)}" if conflicts else ""
      raise state.StateError (f"Integration conflict{detail}")
   message = f"Merge {feature ['branch']} into {feature ['target']}"
   if strategy == "squash":
      message = f"feat: integrate {feature ['name']}"
      return git.commit_tree_parents (tree_oid, [ target_oid ], message), []
   return git.commit_tree_parents (tree_oid, [ target_oid, feature_oid ], message), []


def _target_oids (target: str) -> tuple [str, str, str]:
   local_oid = git.rev_parse (target)
   if not local_oid:
      raise state.StateError (f"Cannot resolve integration target: {target}")
   remote_ref = f"origin/{target}"
   remote_oid = ""
   if git.remote_exists ():
      git.fetch (remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}")
      remote_oid = git.rev_parse (remote_ref)
   target_oid = remote_oid or local_oid
   if not git.is_merged (local_oid, target_oid):
      raise state.StateError (f"Local {target} has commits not present in {remote_ref}")
   return local_oid, remote_oid, target_oid


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


def _review_required (feature: dict [str, Any]) -> bool:
   writers = feature.get ("writers")
   if writers is None:
      creator = str (feature.get ("created_by", ""))
      writers = [] if creator.startswith ("actor:temper:") else [ creator ]
   return bool (repo.get ("review:required", False)) or any (
      writer and not str (writer).startswith ("actor:human:")
      for writer in writers
   )


def plan_done (
   feature: dict [str, Any],
   *,
   actor_id: str,
   into: str = "",
   keep: bool = False,
   pr: bool = False,
   push: bool = False,
   skip_checks: bool = False,
   strategy: str = "",
   persist: bool = True,
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
   local_oid, remote_oid, target_oid = _target_oids (target)
   candidate_oid, rewrites = _candidate (feature, target_oid, chosen_strategy)
   configured = [] if skip_checks else _checks ()
   check_results = run_checks (candidate_oid, configured)
   blockers = [f"Check failed: {value ['name']}" for value in check_results if value ["exit_code"]]
   if _review_required (feature):
      blockers.append ("Human review required")
   payload = {
      "actor_id": actor_id,
      "candidate_oid": candidate_oid,
      "candidate_tree_oid": git.tree (candidate_oid),
      "check_commands": configured,
      "check_results": check_results,
      "feature_id": feature ["feature_id"],
      "feature_oid": git.rev_parse (str (feature ["branch"])),
      "keep": keep,
      "local_target_oid": local_oid,
      "pr": pr,
      "push": push or bool (repo.get ("done:push", False)),
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
   if pr:
      items = [
         { "action": "push", "ref": feature ["branch"] },
         { "action": "pull_request", "base": target, "head": feature ["branch"] },
      ]
   return plans.create (
      "done", str (feature ["name"]),
      scope={ "feature_id": feature ["feature_id"], "repository": git.repo_name () },
      items=items,
      checks=check_results,
      blockers=blockers,
      fingerprint=payload ["state_fingerprint"],
      payload_schema="imp.done-plan.v1",
      payload=payload,
      persist=persist,
   )


def current_plan (feature: dict [str, Any]) -> dict [str, Any] | None:
   return next ((
      plan for plan in plans.all ("done")
      if plan.get ("payload", {}).get ("feature_id") == feature ["feature_id"]
   ), None)


def reusable_plan (feature: dict [str, Any]) -> dict [str, Any] | None:
   """Return the current exact candidate when its bound source has not moved."""

   plan = current_plan (feature)
   if not plan or plan.get ("state") not in { "blocked", "ready" }:
      return None
   payload = plan.get ("payload", {})
   if payload.get ("feature_id") != feature ["feature_id"]:
      return None
   return plan if _state_fingerprint (payload) == payload.get ("state_fingerprint") else None


def review_path (feature_id: str) -> Path:
   return state.root () / "reviews" / f"{identity.key (feature_id)}.json"


def review_receipt (feature_id: str) -> dict [str, Any] | None:
   path = review_path (feature_id)
   if not path.exists ():
      return None
   return state.read (path, "imp.review.v1")


def review_current (plan: dict [str, Any]) -> bool:
   payload = plan ["payload"]
   receipt = review_receipt (str (payload ["feature_id"]))
   return bool (
      receipt
      and receipt.get ("plan_id") == plan ["plan_id"]
      and receipt.get ("target_oid") == payload ["target_oid"]
      and receipt.get ("candidate_oid") == payload ["candidate_oid"]
      and receipt.get ("state_fingerprint") == _state_fingerprint (payload)
      and str (receipt.get ("acknowledged_by", "")).startswith ("actor:human:")
   )


def mark_reviewed (
   plan: dict [str, Any],
   actor_id: str,
   *,
   files: list [str],
   findings: dict [str, int],
) -> dict [str, Any]:
   if not actor_id.startswith ("actor:human:"):
      raise state.StateError ("Only a human actor can mark a candidate reviewed")
   payload = plan ["payload"]
   if _state_fingerprint (payload) != payload ["state_fingerprint"]:
      raise state.StateError ("Integration candidate became stale")
   receipt = {
      "schema": "imp.review.v1",
      "acknowledged_by": actor_id,
      "candidate_oid": payload ["candidate_oid"],
      "commits": _commits (payload ["target_oid"], payload ["candidate_oid"]),
      "feature_id": payload ["feature_id"],
      "files": files,
      "findings": findings,
      "plan_id": plan ["plan_id"],
      "reviewed_at": state.now (),
      "state_fingerprint": payload ["state_fingerprint"],
      "target_oid": payload ["target_oid"],
      "target_ref": payload ["target_ref"],
   }
   state.atomic_write (review_path (str (payload ["feature_id"])), receipt)
   blockers = [value for value in plan.get ("blockers", []) if value != "Human review required"]
   plans.mark (plan, "blocked" if blockers else "ready", blockers=blockers, reviewed_at=state.now ())
   return receipt


def _record_recovery (plan: dict [str, Any], error: Exception, completed: list [str]) -> dict [str, Any]:
   recovery_id = identity.resource ("recovery", "done", str (plan ["label"]), str (len (completed) + 1))
   record = {
      "schema": "imp.recovery.v1",
      "recovery_id": recovery_id,
      "command": "imp done",
      "plan_id": plan ["plan_id"],
      "completed": completed,
      "error": str (error),
      "next": f"imp done --apply {plan ['plan_id']} --yes",
      "created_at": state.now (),
   }
   state.atomic_write (state.root () / "recovery" / f"{identity.key (recovery_id)}.json", record)
   return record


def apply_done (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   if plan.get ("payload_schema") != "imp.done-plan.v1":
      raise state.StateError ("Unsupported integration plan")
   if plan.get ("state") != "ready":
      raise state.StateError (f"Integration plan is {plan.get ('state')}")
   payload = dict (plan ["payload"])
   feature = features.find (str (payload ["feature_id"]))
   if not feature:
      raise state.StateError ("Integration feature is missing")
   direct_receipt = {
      "candidate_oid": payload ["candidate_oid"],
      "feature_id": feature ["feature_id"],
      "mode": "direct",
      "plan_id": plan ["plan_id"],
      "pushed": bool (payload ["push"]),
      "target": payload ["target_ref"],
   }
   completed = []
   try:
      with state.lock (f"done-{identity.slug (str (payload ['target_ref']))}"):
         target_oid = git.rev_parse (str (payload ["target_ref"]))
         finished = (
            not payload ["pr"]
            and feature.get ("state") == "completed"
            and target_oid == payload ["candidate_oid"]
            and not Path (str (feature ["path"])).exists ()
            and not git.ref_exists (str (feature ["branch"]))
         )
         if finished:
            plans.mark (plan, "applied", applied_at=state.now ())
            state.clear_recovery (str (plan ["plan_id"]))
            return direct_receipt
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
            if git.rev_parse (f"origin/{target}") not in {
               payload ["remote_target_oid"], payload ["candidate_oid"],
            }:
               raise state.StateError ("Remote target moved after integration planning")
         if target_oid not in { payload ["local_target_oid"], payload ["candidate_oid"] }:
            raise state.StateError ("Local target moved after integration planning")
         if _state_fingerprint (payload) != payload ["state_fingerprint"]:
            raise state.StateError ("Integration candidate became stale")
         failed = [
            value
            for value in run_checks (payload ["candidate_oid"], payload ["check_commands"])
            if value ["exit_code"]
         ]
         if failed:
            raise state.StateError (f"Integration check failed: {failed [0]['name']}")
         if _review_required (feature) and not review_current (plan):
            raise state.StateError (f"Current human review required; run imp review {feature ['name']}")

         if payload ["pr"]:
            title = git.subject (str (feature ["branch"])) or f"Complete {feature ['name']}"
            body = f"Implements `{feature ['feature_id']}`.\n\nPrepared by Imp plan `{plan ['plan_id']}`."
            if not validate.publishable (f"{title}\n{body}"):
               raise state.StateError ("Pull request text contains AI attribution or an actor ID")
            git.push (set_upstream=True, target=str (feature ["branch"]))
            existing = gh.pr_view (str (feature ["branch"]))
            url = gh.pr_edit (int (existing ["number"]), title, body) if existing else gh.pr_create (
               title, body, str (payload ["target_ref"]), str (feature ["branch"])
            )
            features.complete (feature, actor_id, keep=True, state_name="awaiting-merge")
            completed.extend ([ "push", "pull_request" ])
            plans.mark (plan, "applied", applied_at=state.now ())
            state.clear_recovery (str (plan ["plan_id"]))
            return { "feature_id": feature ["feature_id"], "mode": "pr", "plan_id": plan ["plan_id"], "url": url }

         ref = f"refs/heads/{payload ['target_ref']}"
         if target_oid == payload ["local_target_oid"]:
            git.update_ref_checked (ref, payload ["candidate_oid"], payload ["local_target_oid"])
            for path in git.ref_worktrees (str (payload ["target_ref"])):
               git.reset_at (path, str (payload ["candidate_oid"]))
         completed.append ("integrate")
         if payload ["push"]:
            git.push (ref=str (payload ["target_ref"]))
            completed.append ("push")
         features.complete (feature, actor_id, keep=bool (payload ["keep"]))
         completed.append ("cleanup")
         plans.mark (plan, "applied", applied_at=state.now ())
         state.clear_recovery (str (plan ["plan_id"]))
         return direct_receipt
   except Exception as error:
      _record_recovery (plan, error, completed)
      raise
