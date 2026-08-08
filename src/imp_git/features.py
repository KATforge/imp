import re
import subprocess
from builtins import all as all_values
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from imp_git import config, console, fingerprint, git, identity, plans, repo, runtime, state


def _directory () -> Path:
   return state.root () / "features"


def _path (feature_id: str) -> Path:
   return _directory () / f"{identity.key (feature_id)}.json"


def _claim_path (feature_id: str) -> Path:
   return state.root () / "claims" / f"{identity.key (feature_id)}.json"


def _ttl (value: str = "") -> timedelta:
   raw = value or str (repo.get ("claim:ttl", "8h"))
   match = re.fullmatch (r"(\d+)([hm])", raw)
   if not match:
      raise state.StateError (f"Invalid claim TTL: {raw}")
   count = int (match.group (1))
   return timedelta (hours=count) if match.group (2) == "h" else timedelta (minutes=count)


def _expires_at (ttl: str = "") -> str:
   value = datetime.now (timezone.utc) + _ttl (ttl)
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
         feature = state.read (path, "imp.feature.v1")
         feature ["claim"] = _read_claim (str (feature ["feature_id"]))
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


def _default_path (name: str) -> Path:
   configured = str (repo.get ("worktree:root", "")) or config.get ("worktree:root")
   base = Path (configured).expanduser () if configured else Path.home () / ".worktrees"
   return base / git.repo_name () / identity.slug (name)


def _remote_oid (trunk: str) -> str:
   output = git.capture ("ls-remote", "origin", f"refs/heads/{trunk}")
   lines = output.strip ().splitlines ()
   return lines [0].split () [0] if lines else ""


def _commands () -> list [dict [str, Any]]:
   commands = repo.get ("worktree:setup", []) or []
   for entry in commands:
      argv = entry.get ("run", []) if isinstance (entry, dict) else []
      if not argv or not all_values (isinstance (part, str) for part in argv):
         raise state.StateError ("worktree:setup entries require a run argv array")
   return commands


def _shares () -> list [str]:
   values = repo.get ("worktree:share", []) or []
   if not isinstance (values, list) or not all_values (isinstance (value, str) for value in values):
      raise state.StateError ("worktree:share must be a path array")
   return values


def _descriptor (
   name: str,
   *,
   actor_id: str,
   base: str = "",
   branch: str = "",
   change_id: str = "",
   path: str = "",
   task: str = "",
   target: str = "",
   use: bool = False,
   claim_writer: bool = True,
) -> dict [str, Any]:
   slug = identity.slug (name)
   feature_id = identity.resource ("feature", slug)
   if find (name) or find (feature_id):
      raise state.StateError (f"Feature already exists: {name}")
   branch_name = branch or f"{repo.get ('branch:prefix', 'feature/')}{slug}"
   if git.ref_exists (branch_name):
      raise state.StateError (f"Branch already exists: {branch_name}")
   feature_path = Path (path).expanduser ().resolve () if path else _default_path (slug).resolve ()
   if feature_path.exists ():
      raise state.StateError (f"Worktree path already exists: {feature_path}")
   trunk = target or str (repo.get ("done:target", "")) or git.base_branch ()
   if base:
      if not git.ref_exists (base):
         raise state.StateError (f"Cannot resolve feature base: {base}")
      base_ref = base
      base_oid = git.rev_parse (base)
   elif git.remote_exists ():
      base_ref = f"origin/{trunk}"
      base_oid = _remote_oid (trunk)
   else:
      if not git.ref_exists (trunk):
         raise state.StateError (f"No remote and no local trunk branch: {trunk}")
      base_ref = trunk
      base_oid = git.rev_parse (trunk)
   if not base_oid:
      raise state.StateError (f"Cannot resolve feature base: {base_ref}")
   if change_id:
      identity.validate (change_id, "change")
   return {
      "feature_id": feature_id,
      "name": slug,
      "branch": branch_name,
      "path": str (feature_path),
      "base:ref": base_ref,
      "base:oid": base_oid,
      "target": trunk,
      "task": task.strip (),
      "created_by": actor_id,
      "change_id": change_id,
      "claim_writer": claim_writer,
      "setup": _commands (),
      "share": _shares (),
      "use": use,
   }


def plan_start (
   name: str,
   *,
   actor_id: str,
   base: str = "",
   branch: str = "",
   change_id: str = "",
   path: str = "",
   task: str = "",
   target: str = "",
   use: bool = False,
   claim_writer: bool = True,
   persist: bool = True,
) -> dict [str, Any]:
   """Create an immutable feature-start plan without reserving Git state."""

   descriptor = _descriptor (
      name,
      actor_id=actor_id,
      base=base,
      branch=branch,
      change_id=change_id,
      path=path,
      task=task,
      target=target,
      use=use,
      claim_writer=claim_writer,
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
      *([ { "action": "claim", "held_by": actor_id } ] if descriptor ["claim_writer"] else []),
   ]
   items.extend ({ "action": "share", "path": value } for value in descriptor ["share"])
   items.extend ({ "action": "setup", **value } for value in descriptor ["setup"])
   return plans.create (
      "start",
      str (descriptor ["name"]),
      scope={ "repository": git.repo_name (), "feature": descriptor ["feature_id"] },
      items=items,
      fingerprint=fingerprint.values (bound),
      payload_schema="imp.start-plan.v1",
      payload=descriptor,
      persist=persist,
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


def _share (feature: dict [str, Any], values: list [str]):
   primary = Path (_primary_path ()).resolve ()
   target_root = Path (str (feature ["path"])).resolve ()
   blocked_names = { ".git", ".venv", "build", "dist", "node_modules", "vendor" }
   for relative in values:
      raw = Path (relative)
      if raw.is_absolute () or any (part in blocked_names for part in raw.parts):
         raise state.StateError (f"Unsafe shared worktree path: {relative}")
      source = (primary / raw).resolve ()
      if not source.is_relative_to (primary) or not source.exists ():
         raise state.StateError (f"Shared worktree path is missing or outside the repository: {relative}")
      if source.is_dir () and (source / ".git").exists ():
         raise state.StateError (f"Cannot share a nested repository: {relative}")
      if git.succeeds ("-C", str (primary), "ls-files", "--error-unmatch", "--", relative):
         raise state.StateError (f"Cannot share a tracked path: {relative}")
      if not git.succeeds ("-C", str (primary), "check-ignore", "-q", "--", relative):
         raise state.StateError (f"Shared worktree path is not ignored: {relative}")
      if not git.succeeds ("-C", str (target_root), "check-ignore", "-q", "--", relative):
         raise state.StateError (f"Shared path is not ignored by the new worktree: {relative}")
      target = target_root / raw
      target.parent.mkdir (parents=True, exist_ok=True)
      if target.exists () or target.is_symlink ():
         raise state.StateError (f"Shared worktree target already exists: {relative}")
      target.symlink_to (source, target_is_directory=source.is_dir ())


def _setup (feature: dict [str, Any], commands: list [dict [str, Any]]):
   for entry in commands:
      subprocess.run (entry ["run"], cwd=str (feature ["path"]), check=True)


def apply_start (plan: dict [str, Any]) -> dict [str, Any]:
   """Apply one exact feature-start plan and return the feature record."""

   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   with state.lock ("features"):
      descriptor = _validate_start (plan)
      base_ref = str (descriptor ["base:ref"])
      if base_ref.startswith ("origin/"):
         target = str (descriptor ["target"])
         git.fetch (remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}")
         if git.rev_parse (base_ref) != descriptor ["base:oid"]:
            plans.mark (plan, "stale", stale_at=state.now ())
            raise state.StateError ("Remote trunk moved after the feature plan")
      path = str (descriptor ["path"])
      branch = str (descriptor ["branch"])
      feature_id = str (descriptor ["feature_id"])
      try:
         git.worktree_add (path, branch, str (descriptor ["base:oid"]))
         record = {
            "schema": "imp.feature.v1",
            "feature_id": feature_id,
            "name": descriptor ["name"],
            "branch": branch,
            "path": path,
            "base:ref": descriptor ["base:ref"],
            "base:oid": descriptor ["base:oid"],
            "target": descriptor ["target"],
            "task": descriptor ["task"],
            "created_by": descriptor ["created_by"],
            "writers": [ descriptor ["created_by"] ] if descriptor ["claim_writer"] else [],
            "created_at": state.now (),
            "change_id": descriptor ["change_id"],
            "state": "active",
         }
         _share (record, list (descriptor ["share"]))
         _setup (record, list (descriptor ["setup"]))
         state.atomic_write (_path (feature_id), record)
         claim_record = None
         if descriptor ["claim_writer"]:
            claim_record = _new_claim (feature_id, str (descriptor ["created_by"]))
            state.atomic_write (_claim_path (feature_id), claim_record)
      except Exception:
         if Path (path).exists ():
            git.worktree_remove (path, force=True)
         if git.ref_exists (branch):
            git.delete_branch (branch, force=True)
         _path (feature_id).unlink (missing_ok=True)
         _claim_path (feature_id).unlink (missing_ok=True)
         raise
      if descriptor ["use"]:
         select (record)
      plans.mark (plan, "applied", applied_at=state.now ())
      return { **record, "claim": claim_record, "worktree_state": "live" }


def claim (feature: dict [str, Any], actor_id: str, ttl: str = "") -> dict [str, Any]:
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
         existing ["expires_at"] = _expires_at (ttl)
         state.atomic_write (_claim_path (feature_id), existing)
         _record_writer (feature, actor_id)
         return existing
      value = _new_claim (feature_id, actor_id)
      if ttl:
         value ["expires_at"] = _expires_at (ttl)
      state.atomic_write (_claim_path (feature_id), value)
      _record_writer (feature, actor_id)
      return value


def _record_writer (feature: dict [str, Any], actor_id: str):
   writers = list (feature.get ("writers", []))
   if actor_id in writers:
      return
   writers.append (actor_id)
   record = { key: value for key, value in feature.items () if key not in { "claim", "worktree_state" } }
   record ["writers"] = writers
   state.atomic_write (_path (str (feature ["feature_id"])), record)


def release (feature: dict [str, Any], actor_id: str):
   feature_id = str (feature ["feature_id"])
   with state.lock (identity.key (feature_id)):
      existing = _read_claim (feature_id)
      if not existing:
         return
      if existing.get ("held_by") != actor_id:
         raise state.StateError (f"Feature claim is held by {existing.get ('held_by')}")
      _claim_path (feature_id).unlink ()


def assert_write_access (actor_id: str):
   feature = current ()
   if not feature:
      if bool (repo.get ("feature:required", False)):
         raise state.StateError ("Managed features are required; run imp start")
      return
   existing = _read_claim (str (feature ["feature_id"]))
   if not existing:
      raise state.StateError ("Managed feature has no writer claim")
   if existing.get ("held_by") != actor_id:
      raise state.StateError (
         f"Feature is claimed by {existing.get ('held_by')} until {existing.get ('expires_at')}"
      )
   claim (feature, actor_id)


def _selection_path () -> Path:
   return state.root () / "active.json"


def selection () -> dict [str, Any]:
   path = _selection_path ()
   if path.exists ():
      return state.read (path, "imp.active.v1")
   return {
      "schema": "imp.active.v1",
      "generation": 0,
      "feature_id": None,
      "path": _primary_path (),
      "selected_at": None,
   }


def select (feature: dict [str, Any] | None) -> dict [str, Any]:
   with state.lock ("active"):
      previous = selection ()
      value = {
         "schema": "imp.active.v1",
         "generation": int (previous.get ("generation", 0)) + 1,
         "feature_id": feature.get ("feature_id") if feature else None,
         "path": str (feature.get ("path")) if feature else _primary_path (),
         "selected_at": state.now (),
      }
      state.atomic_write (_selection_path (), value)
      return value


def active () -> dict [str, Any]:
   value = selection ()
   path = Path (str (value ["path"]))
   if not path.is_dir ():
      raise state.StateError (f"Active worktree is missing: {path}")
   feature_id = value.get ("feature_id")
   feature = find (str (feature_id)) if feature_id else None
   return { **value, "feature": feature }


def _remove_fingerprint (feature: dict [str, Any]) -> str:
   path = str (feature ["path"])
   return fingerprint.values ({
      "active": selection (),
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
   delete_branch: bool = False,
   persist: bool = True,
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
   if delete_branch and not git.is_merged (str (feature ["branch"]), str (feature ["target"])):
      blockers.append (f"Branch is not merged into {feature ['target']}")
   return plans.create (
      "worktree-remove",
      str (feature ["name"]),
      scope={ "feature_id": feature ["feature_id"] },
      items=[
         { "action": "remove_worktree", "path": feature ["path"] },
         *([ { "action": "delete_branch", "branch": feature ["branch"] } ] if delete_branch else []),
         { "action": "release_claim", "feature_id": feature ["feature_id"] },
      ],
      fingerprint=_remove_fingerprint (feature),
      payload_schema="imp.worktree-remove-plan.v1",
      payload={
         "actor_id": actor_id,
         "delete_branch": delete_branch,
         "feature_id": feature ["feature_id"],
      },
      blockers=blockers,
      persist=persist,
   )


def apply_remove (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   """Apply an exact clean-worktree removal plan."""

   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   if plan.get ("payload_schema") != "imp.worktree-remove-plan.v1":
      raise state.StateError ("Unsupported worktree removal plan")
   payload = dict (plan ["payload"])
   if payload.get ("actor_id") != actor_id:
      raise state.StateError (f"Worktree removal plan belongs to {payload.get ('actor_id')}")
   feature = find (str (payload ["feature_id"]))
   if not feature or _remove_fingerprint (feature) != plan.get ("fingerprint"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Worktree removal plan is stale")
   with state.lock ("features"):
      git.worktree_remove (str (feature ["path"]))
      release (feature, actor_id)
      if payload ["delete_branch"] and not git.delete_branch (str (feature ["branch"])):
         raise state.StateError (f"Could not delete branch {feature ['branch']}")
      stored = state.read (_path (str (feature ["feature_id"])), "imp.feature.v1")
      stored ["state"] = "removed"
      stored ["removed_at"] = state.now ()
      state.atomic_write (_path (str (feature ["feature_id"])), stored)
      if selection ().get ("feature_id") == feature ["feature_id"]:
         select (None)
      plans.mark (plan, "applied", applied_at=state.now ())
   return {
      "branch_deleted": bool (payload ["delete_branch"]),
      "feature_id": feature ["feature_id"],
      "path": feature ["path"],
   }


def complete (
   feature: dict [str, Any],
   actor_id: str,
   *,
   keep: bool = False,
   state_name: str = "completed",
) -> dict [str, Any]:
   """Mark a feature complete and optionally remove its clean local resources."""

   feature_id = str (feature ["feature_id"])
   with state.lock (f"feature-{identity.key (feature_id)}"):
      record = state.read (_path (feature_id), "imp.feature.v1")
      record ["state"] = state_name
      record ["completed_at"] = state.now ()
      state.atomic_write (_path (feature_id), record)

   if keep:
      return record

   if Path (str (feature ["path"])).exists ():
      if not git.clean_at (str (feature ["path"])):
         raise state.StateError ("Completed feature worktree became dirty")
      git.worktree_remove (str (feature ["path"]))
   _claim_path (feature_id).unlink (missing_ok=True)
   if git.ref_exists (str (feature ["branch"])):
      if not git.delete_branch (str (feature ["branch"]), force=True):
         raise state.StateError (f"Could not delete integrated branch {feature ['branch']}")
   if selection ().get ("feature_id") == feature_id:
      select (None)

   return record
