import json
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from imp_git import features, fingerprint, git, layers, locks, plans, state


def _configured_checks () -> list [dict [str, Any]] | None:
   values = git.config_get_all ("imp.check")
   if not values:
      return None
   if values == [ "none" ]:
      return []
   return [ { "name": value, "run": shlex.split (value) } for value in values ]


def _package_check (root: Path) -> list [dict [str, Any]]:
   try:
      scripts = json.loads ((root / "package.json").read_text ()).get ("scripts", {})
   except (json.JSONDecodeError, OSError):
      return []
   script = str (scripts.get ("test") or "")
   if not script or "no test specified" in script:
      return []
   return [ { "name": "npm test", "run": [ "npm", "test" ] } ]


def _composer_check (root: Path) -> list [dict [str, Any]]:
   try:
      scripts = json.loads ((root / "composer.json").read_text ()).get ("scripts", {})
   except (json.JSONDecodeError, OSError):
      return []
   if not scripts.get ("test"):
      return []
   return [ { "name": "composer test", "run": [ "composer", "test" ] } ]


def _pytest_check (root: Path) -> list [dict [str, Any]]:
   pyproject = root / "pyproject.toml"
   try:
      if "pytest" not in pyproject.read_text ():
         return []
   except OSError:
      return []
   if (root / "uv.lock").is_file () and shutil.which ("uv"):
      return [ { "name": "pytest", "run": [ "uv", "run", "pytest", "-q" ] } ]
   return [ { "name": "pytest", "run": [ "pytest", "-q" ] } ]


def _make_check (root: Path) -> list [dict [str, Any]]:
   try:
      lines = (root / "Makefile").read_text ().splitlines ()
   except OSError:
      return []
   if not any (line.startswith ("test:") for line in lines):
      return []
   return [ { "name": "make test", "run": [ "make", "test" ] } ]


def _checks () -> list [dict [str, Any]]:
   """Return this repository's test commands: imp.check entries, or what the project declares.

   Detection is deterministic and first-match: package.json test script, composer test
   script, a pyproject mentioning pytest, then a Makefile test target. Set imp.check to
   override, or to the single value "none" to disable checks.
   """

   configured = _configured_checks ()
   if configured is not None:
      return configured
   root = Path (git.repo_root ())
   for detect in (_package_check, _composer_check, _pytest_check, _make_check):
      found = detect (root)
      if found:
         return found
   return []


def configured_checks () -> list [dict [str, Any]]:
   return _checks ()


def _sweep_stale ():
   removed = False
   for root in Path (tempfile.gettempdir ()).glob ("imp-*"):
      try:
         if not root.is_dir () or time.time () - root.stat ().st_mtime < 2 * 60 * 60:
            continue
         shutil.rmtree (root, ignore_errors=True)
         removed = True
      except OSError:
         continue
   if removed:
      git.prune_worktrees ()


def _temporary_worktree (ref: str, prefix: str):
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
            check ["run"], cwd=path, capture_output=True, text=True, timeout=900, check=False,
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
   return git.capture ("rev-list", "--reverse", f"{target_oid}..{feature_oid}").splitlines ()


def _rebase_candidate (target_oid: str, feature_oid: str) -> tuple [str, list [dict [str, str]]]:
   base_oid = git.merge_base (target_oid, feature_oid)
   before = _commits (base_oid, feature_oid)
   path, cleanup = _temporary_worktree (feature_oid, "rebase")
   try:
      result = git.run_at (
         str (path), "rebase", "--onto", target_oid, base_oid, feature_oid,
         check=False, env={ "GIT_SEQUENCE_EDITOR": ":", "GIT_EDITOR": ":" },
      )
      if result.returncode:
         names = git.run_at (str (path), "diff", "--name-only", "--diff-filter=U", check=False).stdout.splitlines ()
         detail = f": {', '.join (names)}" if names else ""
         raise state.StateError (f"Integration conflict{detail}")
      candidate_oid = git.run_at (str (path), "rev-parse", "HEAD").stdout.strip ()
      after = _commits (target_oid, candidate_oid)
      return candidate_oid, [
         { "from": old, "to": new }
         for old, new in zip (before, after, strict=False)
         if old != new
      ]
   finally:
      cleanup ()


def _candidate (feature: dict [str, Any], target_oid: str) -> tuple [str, list [dict [str, str]]]:
   feature_oid = git.rev_parse (str (feature ["branch"]))
   if git.is_merged (feature_oid, target_oid):
      return target_oid, []
   if git.is_merged (target_oid, feature_oid):
      return feature_oid, []
   base_oid = git.merge_base (target_oid, feature_oid)
   if not any (git.published (oid) for oid in _commits (base_oid, feature_oid)):
      return _rebase_candidate (target_oid, feature_oid)
   tree_oid, conflicts = git.merge_tree (target_oid, feature_oid)
   if not tree_oid:
      detail = f": {', '.join (conflicts)}" if conflicts else ""
      raise state.StateError (f"Integration conflict{detail}")
   message = f"Merge {feature ['branch']} into {feature ['target']}"
   return git.commit_tree_parents (tree_oid, [ target_oid, feature_oid ], message), []


def _resurrected (base_oid: str, target_oid: str, candidate_oid: str) -> list [str]:
   removed = set (git.capture ("diff", "--name-only", "--diff-filter=D", base_oid, target_oid).splitlines ())
   present = set (git.capture ("ls-tree", "-r", "--name-only", candidate_oid).splitlines ())
   return sorted (removed & present)


def _target_oids (target: str) -> tuple [str, str, str]:
   local_oid = git.rev_parse (target)
   if not local_oid:
      raise state.StateError (f"Cannot resolve integration target: {target}")
   remote_oid = ""
   if git.remote_exists ():
      git.fetch (remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}")
      remote_oid = git.rev_parse (f"origin/{target}")
   if not remote_oid or git.is_merged (remote_oid, local_oid):
      return local_oid, remote_oid, local_oid
   if git.is_merged (local_oid, remote_oid):
      return local_oid, remote_oid, remote_oid
   raise state.StateError (f"Local {target} and origin/{target} have diverged")


def target_state (target: str) -> tuple [str, str, str]:
   return _target_oids (target)


def _state_fingerprint (payload: dict [str, Any]) -> str:
   feature = features.find (str (payload ["branch"]))
   if not feature:
      return ""
   path = str (feature ["path"])
   return fingerprint.values ({
      "candidate_oid": payload ["candidate_oid"],
      "candidate_tree_oid": payload ["candidate_tree_oid"],
      "feature_oid": git.rev_parse (str (feature ["branch"])),
      "status": git.capture ("-C", path, "status", "--porcelain=v1", "-z") if path else "",
      "target_oid": payload ["target_oid"],
      "target_ref": payload ["target_ref"],
   })


def plan_done (
   feature: dict [str, Any],
   *,
   resolved_target: tuple [str, str, str] | None = None,
) -> dict [str, Any]:
   path = str (feature ["path"])
   if path and not git.clean_at (path):
      raise state.StateError ("Feature worktree has uncommitted changes")
   target = str (feature.get ("target") or git.base_branch ())
   local_oid, remote_oid, target_oid = resolved_target or _target_oids (target)
   candidate_oid, rewrites = _candidate (feature, target_oid)
   blockers = [
      f"Target checkout has uncommitted work: {path}"
      for path in git.ref_worktrees (target)
      if not git.clean_at (path)
   ]
   checks = _checks ()
   check_results = [] if blockers else run_checks (candidate_oid, checks)
   blockers.extend (f"Check failed: {value ['name']}" for value in check_results if value ["exit_code"])
   feature_oid = git.rev_parse (str (feature ["branch"]))
   resurrected = _resurrected (git.merge_base (target_oid, feature_oid), target_oid, candidate_oid)
   if resurrected:
      blockers.append (f"Candidate restores deleted paths: {', '.join (resurrected [:5])}")
   taken = locks.foreign (target)
   if taken:
      blockers.append (f"{target} is locked by {taken ['actor']} ({taken ['name']}) until {taken ['expires_at']}")
   payload = {
      "branch": feature ["branch"],
      "candidate_oid": candidate_oid,
      "candidate_tree_oid": git.tree (candidate_oid),
      "check_results": check_results,
      "diff": git.capture ("diff", "--binary", target_oid, candidate_oid),
      "feature_oid": feature_oid,
      "local_target_oid": local_oid,
      "remote_target_oid": remote_oid,
      "rewrites": rewrites,
      "state_fingerprint": "",
      "target_oid": target_oid,
      "target_ref": target,
   }
   payload ["state_fingerprint"] = _state_fingerprint (payload)
   return plans.build (
      "done", str (feature ["name"]),
      scope={ "branch": feature ["branch"], "repository": git.repo_name () },
      items=[
         { "action": "integrate", "candidate_oid": candidate_oid, "target": target },
         { "action": "remove", "branch": feature ["branch"] },
      ],
      checks=check_results,
      blockers=blockers,
      fingerprint=payload ["state_fingerprint"],
      payload_schema="imp.done-plan.v3",
      payload=payload,
   )


def _validate (plan: dict [str, Any]):
   if plan.get ("state") != "ready" or plan.get ("payload_schema") != "imp.done-plan.v3":
      raise state.StateError ("Integration plan is not ready")
   payload = plan ["payload"]
   feature = features.find (str (payload ["branch"]))
   if not feature:
      raise state.StateError ("Integration feature is missing")
   path = str (feature ["path"])
   if path and not git.clean_at (path):
      raise state.StateError ("Feature worktree became dirty")
   for worktree_path in git.ref_worktrees (str (payload ["target_ref"])):
      if not git.clean_at (worktree_path):
         raise state.StateError (f"Target worktree is dirty: {worktree_path}")
   if git.rev_parse (str (feature ["branch"])) != payload ["feature_oid"]:
      raise state.StateError ("Feature moved after integration planning")
   if git.remote_exists () and payload ["remote_target_oid"]:
      target = str (payload ["target_ref"])
      git.fetch (remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}")
      if git.rev_parse (f"origin/{target}") not in { payload ["remote_target_oid"], payload ["candidate_oid"] }:
         raise state.StateError ("Remote target moved after integration planning")
   target_oid = git.rev_parse (str (payload ["target_ref"]))
   if target_oid not in { payload ["local_target_oid"], payload ["candidate_oid"] }:
      raise state.StateError ("Local target moved after integration planning")
   if _state_fingerprint (payload) != payload ["state_fingerprint"]:
      raise state.StateError ("Integration candidate became stale")
   return payload, feature, target_oid


def apply_done (plan: dict [str, Any]) -> dict [str, Any]:
   payload, feature, target_oid = _validate (plan)
   if target_oid == payload ["local_target_oid"]:
      _, layer = layers.stage (
         str (payload ["branch"]).removeprefix (features.PREFIX),
         str (payload ["candidate_oid"]),
         str (payload ["local_target_oid"]),
      )
      git.update_refs (
         [
            f"update refs/heads/{payload ['target_ref']} {payload ['candidate_oid']} {payload ['local_target_oid']}",
            *layer,
         ],
         message=f"imp done: {payload ['branch']}",
      )
      for path in git.ref_worktrees (str (payload ["target_ref"])):
         git.reset_at (path, str (payload ["candidate_oid"]))
   plans.mark (plan, "applied", applied_at=state.now ())
   features.complete (feature, branch_oid=str (payload ["feature_oid"]))
   return {
      "branch": payload ["branch"],
      "candidate_oid": payload ["candidate_oid"],
      "target": payload ["target_ref"],
   }
