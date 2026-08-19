import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from imp_git import config, console, fingerprint, git, identity, plans, runtime, state


def _drop_task (value: dict [str, Any]) -> dict [str, Any]:
   """Forget the free-text intent no command ever read."""

   value.pop ("task", None)
   value ["schema"] = "imp.feature.v2"

   return value


_MIGRATIONS: dict [str, state.Migration] = { "imp.feature.v1": _drop_task }


def _directory () -> Path:
   return state.root () / "features"


def _path (feature_id: str) -> Path:
   return _directory () / f"{identity.key (feature_id)}.json"


def _claim_path (feature_id: str) -> Path:
   return state.root () / "claims" / f"{identity.key (feature_id)}.json"


def _expires_at () -> str:
   value = datetime.now (timezone.utc) + timedelta (hours=8)
   return value.isoformat ().replace ("+00:00", "Z")


def _is_expired (claim_record: dict [str, Any]) -> bool:
   raw = str (claim_record.get ("expires_at", ""))
   if not raw:
      return True
   try:
      expires = datetime.fromisoformat (raw.replace ("Z", "+00:00"))
   except ValueError:
      return True
   return expires <= datetime.now (timezone.utc)


def _read_claim (feature_id: str) -> dict [str, Any] | None:
   path = _claim_path (feature_id)
   if not path.exists ():
      return None
   return state.read (path, "imp.claim.v1")


def _worktree_state (feature: dict [str, Any]) -> str:
   expected_path = str (Path (str (feature ["path"])).resolve ())
   expected_branch = f"refs/heads/{feature ['branch']}"
   for entry in git.worktrees ():
      if str (Path (entry.get ("worktree", "")).resolve ()) != expected_path:
         continue
      return "live" if entry.get ("branch") == expected_branch else "branch-mismatch"
   return "missing"


def all () -> list [dict [str, Any]]:
   """List retained features with reconciled worktree and claim state."""

   directory = _directory ()
   if not directory.exists ():
      return []
   values = []
   for path in directory.glob ("feature--*.json"):
      try:
         feature = state.read (path, "imp.feature.v2", _MIGRATIONS)
         claim_record = _read_claim (str (feature ["feature_id"]))
         feature ["claim"] = None if claim_record and _is_expired (claim_record) else claim_record
         feature ["worktree_state"] = _worktree_state (feature)
         values.append (feature)
      except state.StateError:
         continue
   return sorted (values, key=lambda value: str (value.get ("created_at", "")))


def find (value: str) -> dict [str, Any] | None:
   matches = [
      feature for feature in all ()
      if feature.get ("feature_id") == value or feature.get ("name") == value
   ]
   if len (matches) > 1:
      raise state.StateError (f"Several features are named {value}; use the feature ID")
   return matches [0] if matches else None


def eligible (
   states: set [str] | None = None,
   *,
   live: bool = True,
) -> list [dict [str, Any]]:
   allowed = states or { "active" }
   return [
      feature
      for feature in reversed (all ())
      if feature.get ("state") in allowed and (not live or feature.get ("worktree_state") == "live")
   ]


def label (feature: dict [str, Any]) -> str:
   return f"{feature ['name']} · {feature ['state']} · {feature ['branch']}"


def pick (title: str, values: list [dict [str, Any]]) -> dict [str, Any]:
   if not values:
      raise state.StateError ("No eligible managed features")
   if runtime.options.json or runtime.options.no_input:
      raise state.StateError ("Pass an explicit feature name or ID")
   labels = [ label (feature) for feature in values ]
   selected = console.choose (title, labels)
   return values [labels.index (selected)]


def resolve (
   value: str = "",
   *,
   states: set [str] | None = None,
   title: str = "Select feature",
   live: bool = True,
) -> dict [str, Any]:
   allowed = states or { "active" }
   if not value:
      return pick (title, eligible (allowed, live=live))
   feature = find (value)
   if not feature:
      raise state.StateError (f"Unknown managed feature: {value}")
   if feature.get ("state") not in allowed:
      raise state.StateError (f"Feature {feature ['name']} is {feature.get ('state')}")
   if live and feature.get ("worktree_state") != "live":
      raise state.StateError (f"Feature {feature ['name']} worktree is {feature.get ('worktree_state')}")
   return feature


def current () -> dict [str, Any] | None:
   root = Path (git.repo_root ()).resolve ()
   return next ((feature for feature in all () if Path (str (feature ["path"])).resolve () == root), None)


def _primary_path () -> str:
   entries = git.worktrees ()
   if not entries:
      return git.repo_root ()
   return str (Path (entries [0].get ("worktree", git.repo_root ())).resolve ())


def _managed_root () -> Path:
   configured = config.get ("worktree:root")
   base = Path (configured).expanduser () if configured else Path.home () / ".worktrees"
   return base / git.repo_name ()


def _default_path (name: str) -> Path:
   return _managed_root () / identity.slug (name)


def _trunk_base (trunk: str) -> tuple [str, str]:
   """Prefer local trunk when it merely leads the remote, the ordinary state after integrating.

   Basing on the remote there would silently drop every feature already integrated and not
   yet pushed. Anything else, including a genuine divergence, still branches from the remote.
   """

   remote_oid = _remote_oid (trunk)
   local_oid = git.rev_parse (trunk)
   if local_oid and remote_oid and git.is_merged (remote_oid, local_oid):
      return trunk, local_oid

   return f"origin/{trunk}", remote_oid


def _remote_oid (trunk: str) -> str:
   output = git.capture ("ls-remote", "origin", f"refs/heads/{trunk}")
   lines = output.strip ().splitlines ()
   return lines [0].split () [0] if lines else ""


def _descriptor (
   name: str,
   *,
   actor_id: str,
   span: list [str] | None = None,
) -> dict [str, Any]:
   slug = identity.slug (name)
   feature_id = identity.resource ("feature", slug)
   if find (name) or find (feature_id):
      raise state.StateError (f"Feature already exists: {name}")
   branch_name = f"feature/{slug}"
   if git.ref_exists (branch_name):
      raise state.StateError (f"Branch already exists: {branch_name}")
   feature_path = _default_path (slug).resolve ()
   if feature_path.exists ():
      raise state.StateError (f"Worktree path already exists: {feature_path}")
   trunk = git.base_branch ()
   if git.remote_exists ():
      base_ref, base_oid = _trunk_base (trunk)
   else:
      if not git.ref_exists (trunk):
         raise state.StateError (f"No remote and no local trunk branch: {trunk}")
      base_ref = trunk
      base_oid = git.rev_parse (trunk)
   if not base_oid:
      raise state.StateError (f"Cannot resolve feature base: {base_ref}")
   return {
      "feature_id": feature_id,
      "name": slug,
      "branch": branch_name,
      "path": str (feature_path),
      "base:ref": base_ref,
      "base:oid": base_oid,
      "target": trunk,
      "created_by": actor_id,
      "span": list (span or []),
   }


def plan_start (
   name: str,
   *,
   actor_id: str,
   span: list [str] | None = None,
) -> dict [str, Any]:
   """Create an immutable feature-start plan without reserving Git state."""

   descriptor = _descriptor (
      name,
      actor_id=actor_id,
      span=span,
   )
   bound = {
      "base:oid": descriptor ["base:oid"],
      "branch": descriptor ["branch"],
      "feature_id": descriptor ["feature_id"],
      "path": descriptor ["path"],
   }
   items = [
      { "action": "create_branch", "branch": descriptor ["branch"], "base": descriptor ["base:oid"] },
      { "action": "create_worktree", "path": descriptor ["path"] },
      { "action": "claim", "held_by": actor_id },
   ]
   return plans.build (
      "start",
      str (descriptor ["name"]),
      scope={ "repository": git.repo_name (), "feature": descriptor ["feature_id"] },
      items=items,
      fingerprint=fingerprint.values (bound),
      payload_schema="imp.start-plan.v1",
      payload=descriptor,
   )


def _validate_start (plan: dict [str, Any]) -> dict [str, Any]:
   descriptor = dict (plan.get ("payload", {}))
   if plan.get ("payload_schema") != "imp.start-plan.v1":
      raise state.StateError ("Unsupported feature-start plan payload")
   if find (str (descriptor ["name"])) or git.ref_exists (str (descriptor ["branch"])):
      raise state.StateError ("Feature-start plan is stale")
   if Path (str (descriptor ["path"])).exists ():
      raise state.StateError ("Feature-start plan is stale")
   base_ref = str (descriptor ["base:ref"])
   if base_ref.startswith ("origin/"):
      current_oid = _remote_oid (str (descriptor ["target"]))
   else:
      current_oid = git.rev_parse (base_ref)
   bound = {
      "base:oid": current_oid,
      "branch": descriptor ["branch"],
      "feature_id": descriptor ["feature_id"],
      "path": descriptor ["path"],
   }
   if fingerprint.values (bound) != plan.get ("fingerprint"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Feature-start plan is stale")
   return descriptor


def _new_claim (feature_id: str, actor_id: str) -> dict [str, Any]:
   timestamp = state.now ()
   return {
      "schema": "imp.claim.v1",
      "feature_id": feature_id,
      "held_by": actor_id,
      "created_at": timestamp,
      "renewed_at": timestamp,
      "expires_at": _expires_at (),
   }


def _discard_start (path: str, branch: str, feature_id: str):
   if Path (path).exists ():
      git.worktree_remove (path, force=True)
   if git.ref_exists (branch):
      git.delete_branch (branch, force=True)
   _path (feature_id).unlink (missing_ok=True)
   _claim_path (feature_id).unlink (missing_ok=True)


def apply_start (plan: dict [str, Any]) -> dict [str, Any]:
   """Apply one exact feature-start plan and return the feature record."""

   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   base_ref = str (plan.get ("payload", {}).get ("base:ref", ""))
   if base_ref.startswith ("origin/"):
      target = str (plan ["payload"] ["target"])
      git.fetch (remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}")
   with state.lock ("features"):
      descriptor = _validate_start (plan)
      if base_ref.startswith ("origin/") and git.rev_parse (base_ref) != descriptor ["base:oid"]:
         plans.mark (plan, "stale", stale_at=state.now ())
         raise state.StateError ("Remote trunk moved after the feature plan")
      path = str (descriptor ["path"])
      branch = str (descriptor ["branch"])
      feature_id = str (descriptor ["feature_id"])
      try:
         git.worktree_add (path, branch, str (descriptor ["base:oid"]))
         record = {
            "schema": "imp.feature.v2",
            "feature_id": feature_id,
            "name": descriptor ["name"],
            "branch": branch,
            "path": path,
            "base:ref": descriptor ["base:ref"],
            "base:oid": descriptor ["base:oid"],
            "target": descriptor ["target"],
            "created_by": descriptor ["created_by"],
            "created_at": state.now (),
            "span": list (descriptor.get ("span") or []),
            "state": "active",
         }
         state.atomic_write (_path (feature_id), record)
         claim_record = _new_claim (feature_id, str (descriptor ["created_by"]))
         state.atomic_write (_claim_path (feature_id), claim_record)
      except Exception:
         _discard_start (path, branch, feature_id)
         raise
   plans.mark (plan, "applied", applied_at=state.now ())
   return { **record, "claim": claim_record, "worktree_state": "live" }


def discard_start (feature: dict [str, Any]):
   """Undo one applied feature start, so a partial span leaves nothing behind."""

   _discard_start (str (feature ["path"]), str (feature ["branch"]), str (feature ["feature_id"]))


def claim (feature: dict [str, Any], actor_id: str) -> dict [str, Any]:
   """Acquire or renew a feature's sole writer claim."""

   feature_id = str (feature ["feature_id"])
   with state.lock (identity.key (feature_id)):
      existing = _read_claim (feature_id)
      if existing and _is_expired (existing):
         existing = None
      if existing:
         held_by = existing.get ("held_by")
         if held_by != actor_id:
            raise state.StateError (
               f"Feature has an active claim held by {held_by} until {existing.get ('expires_at')}"
            )
         existing ["renewed_at"] = state.now ()
         existing ["expires_at"] = _expires_at ()
         state.atomic_write (_claim_path (feature_id), existing)
         return existing
      value = _new_claim (feature_id, actor_id)
      state.atomic_write (_claim_path (feature_id), value)
      return value


def assert_write_access (actor_id: str):
   feature = current ()
   if not feature:
      return
   claim (feature, actor_id)


def _remove_fingerprint (feature: dict [str, Any]) -> str:
   path = str (feature ["path"])
   return fingerprint.values ({
      "branch": feature ["branch"],
      "branch_oid": git.rev_parse (str (feature ["branch"])),
      "claim": _read_claim (str (feature ["feature_id"])),
      "feature_id": feature ["feature_id"],
      "path": path,
      "status": git.capture ("-C", path, "status", "--porcelain=v1"),
   })


def plan_remove (
   feature: dict [str, Any],
   *,
   actor_id: str,
) -> dict [str, Any]:
   """Plan removal of one clean managed worktree."""

   blockers = []
   claim_record = _read_claim (str (feature ["feature_id"]))
   if claim_record and claim_record.get ("held_by") != actor_id and not _is_expired (claim_record):
      blockers.append (f"Active writer claim held by {claim_record.get ('held_by')}")
   dirty = git.capture ("-C", str (feature ["path"]), "status", "--porcelain=v1")
   if dirty:
      blockers.append ("Worktree has uncommitted changes")
   if feature.get ("worktree_state") != "live":
      blockers.append (f"Worktree record is {feature.get ('worktree_state')}")
   return plans.build (
      "worktree-remove",
      str (feature ["name"]),
      scope={ "feature_id": feature ["feature_id"] },
      items=[
         { "action": "remove_worktree", "path": feature ["path"] },
         { "action": "delete_branch", "branch": feature ["branch"] },
         { "action": "delete_record", "feature": feature ["feature_id"] },
      ],
      fingerprint=_remove_fingerprint (feature),
      payload_schema="imp.remove-plan.v2",
      payload={
         "actor_id": actor_id,
         "feature_id": feature ["feature_id"],
      },
      blockers=blockers,
   )


def apply_remove (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   """Apply an exact clean-worktree removal plan."""

   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   if plan.get ("payload_schema") != "imp.remove-plan.v2":
      raise state.StateError ("Unsupported worktree removal plan")
   payload = dict (plan ["payload"])
   if payload.get ("actor_id") != actor_id:
      raise state.StateError (f"Worktree removal plan belongs to {payload.get ('actor_id')}")
   feature = find (str (payload ["feature_id"]))
   if not feature or _remove_fingerprint (feature) != plan.get ("fingerprint"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Worktree removal plan is stale")
   with state.lock (f"feature-{identity.key (str (feature ['feature_id']))}"):
      _leave (str (feature ["path"]))
      git.worktree_remove (str (feature ["path"]))
      if not git.delete_branch (str (feature ["branch"]), force=True):
         raise state.StateError (f"Could not delete branch {feature ['branch']}")
      _claim_path (str (feature ["feature_id"])).unlink (missing_ok=True)
      _path (str (feature ["feature_id"])).unlink (missing_ok=True)
      plans.mark (plan, "applied", applied_at=state.now ())
   return {
      "feature_id": feature ["feature_id"],
      "path": feature ["path"],
   }


def _leave (path: str):
   """Step out of a worktree before removing it, so the caller keeps a live directory."""

   target = Path (path).resolve ()
   try:
      current = Path.cwd ().resolve ()
   except OSError:
      current = None
   if current and (current == target or target in current.parents):
      os.chdir (_primary_path ())


def complete (
   feature: dict [str, Any],
   *,
   branch_oid: str = "",
) -> dict [str, Any]:
   feature_id = str (feature ["feature_id"])
   branch = str (feature ["branch"])
   if branch_oid and git.rev_parse (branch) != branch_oid:
      raise state.StateError (f"Feature branch changed: {branch}")
   with state.lock (f"feature-{identity.key (feature_id)}"):
      if Path (str (feature ["path"])).exists ():
         if not git.clean_at (str (feature ["path"])):
            raise state.StateError ("Completed feature worktree became dirty")
         _leave (str (feature ["path"]))
         git.worktree_remove (str (feature ["path"]), force=True)
      if git.ref_exists (branch):
         try:
            git.delete_branch_checked (branch, branch_oid or git.rev_parse (branch))
         except subprocess.CalledProcessError as error:
            raise state.StateError (f"Integrated branch changed: {branch}") from error
      _claim_path (feature_id).unlink (missing_ok=True)
      _path (feature_id).unlink ()
   return { **feature, "state": "completed", "completed_at": state.now () }
