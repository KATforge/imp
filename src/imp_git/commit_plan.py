import json
import shutil
from fnmatch import fnmatch
from typing import Any

from imp_git import ai, features, fingerprint, git, hygiene, identity, patches, plans, prompts, repo, state, validate


def _scope (all_changes: bool, staged: bool) -> tuple [str, list [str]]:
   staged_paths = git.changed_paths (staged=True)
   if staged:
      return "staged", staged_paths
   if all_changes or not staged_paths:
      return "all", git.changed_paths (all_changes=True)

   return "staged", staged_paths


def _allocate (sizes: list [int], budget: int) -> list [int]:
   """Preserve small inputs and divide the remaining budget across large ones."""

   limits = [0] * len (sizes)
   remaining = set (range (len (sizes)))
   available = max (0, budget)
   while remaining:
      share = available // len (remaining)
      complete = {index for index in remaining if sizes [index] <= share}
      if not complete:
         for offset, index in enumerate (sorted (remaining)):
            limits [index] = share + (1 if offset < available % len (remaining) else 0)
         break
      for index in complete:
         limits [index] = sizes [index]
         available -= sizes [index]
      remaining -= complete
   return limits


def _diffs (changes: list [dict [str, str]]) -> str:
   headers = [f"--- {change ['id']} ---\n" for change in changes]
   overhead = sum (len (header) for header in headers) + max (0, len (headers) - 1)
   if len (headers) > ai.MAX_DIFF_LINES or overhead > ai.MAX_DIFF_CHARS:
      raise state.StateError ("Too many change sections for one commit plan")
   line_budget = max (0, ai.MAX_DIFF_LINES - len (headers))
   line_limits = _allocate ([len (change ["patch"].splitlines ()) for change in changes], line_budget)
   bodies = [
      "\n".join (change ["patch"].splitlines () [:limit])
      for change, limit in zip (changes, line_limits, strict=True)
   ]
   char_limits = _allocate ([len (body) for body in bodies], ai.MAX_DIFF_CHARS - overhead)
   return "\n".join (
      f"{header}{body [:limit]}"
      for header, body, limit in zip (headers, bodies, char_limits, strict=True)
   )


def _groups (
   changes: list [dict [str, str]],
   whisper: str,
   single: bool,
) -> list [dict [str, Any]]:
   diffs = _diffs (changes)
   branch = git.branch ()
   change_ids = [change ["id"] for change in changes]
   if single or len (changes) == 1:
      message = ai.commit_message (prompts.commit (diffs, branch, whisper))
      return [ {
         "message": message,
         "files": sorted ({ change ["path"] for change in changes }),
         "changes": change_ids,
      } ]

   response = ai.strip_fences (ai.smart (prompts.split_changes (diffs, len (changes), branch, whisper)))
   try:
      groups = json.loads (response)
   except json.JSONDecodeError as error:
      raise state.StateError ("AI returned an invalid commit plan") from error
   if not isinstance (groups, list) or not groups:
      raise state.StateError ("AI returned an empty commit plan")

   covered: list [str] = []
   normalized = []
   by_id = { change ["id"]: change for change in changes }
   for group in groups:
      if not isinstance (group, dict):
         raise state.StateError ("AI commit groups must be objects")
      message = str (group.get ("message", ""))
      selected = group.get ("changes", [])
      if not validate.commit (message, int (repo.get ("commit:max_subject", 72))):
         raise state.StateError (f"Invalid Conventional Commit message: {message}")
      if not isinstance (selected, list) or not all (isinstance (change, str) for change in selected):
         raise state.StateError ("AI commit groups require change lists")
      if not selected:
         raise state.StateError ("AI commit groups cannot be empty")
      covered.extend (selected)
      normalized.append ({
         "message": message,
         "files": sorted ({ by_id [change] ["path"] for change in selected if change in by_id }),
         "changes": selected,
      })

   if len (covered) != len (set (covered)):
      raise state.StateError ("AI assigned a path to more than one commit")
   if set (covered) != set (change_ids):
      raise state.StateError ("AI commit groups do not cover every selected change")

   return normalized


def create (
   *,
   actor_id: str,
   all_changes: bool = False,
   amend: bool = False,
   exclude: list [str] | None = None,
   single: bool = False,
   staged: bool = False,
   whisper: str = "",
   persist: bool = True,
) -> dict [str, Any]:
   """Build and optionally persist one exact commit plan."""

   mode, paths = _scope (all_changes, staged)
   if amend and git.published ("HEAD"):
      raise state.StateError ("Cannot amend published history")
   staged_paths = git.changed_paths (staged=True)
   if exclude:
      paths = [path for path in paths if not any (fnmatch (path, pattern) for pattern in exclude)]
   paths = git.committable_paths (paths)
   if not paths:
      raise state.StateError ("Nothing selected to commit")

   warnings = hygiene.inspect (paths)
   changes, desired_tree = patches.changes (paths, mode)
   groups = _groups (changes, whisper, single)
   feature = features.current ()
   label = str (feature ["name"]) if feature else identity.slug (git.branch () or "detached")
   head = git.rev_parse ("HEAD")
   branch_ref = git.current_ref ()
   if not branch_ref:
      raise state.StateError ("Commit planning requires an attached branch")

   payload = {
      "actor_id": actor_id,
      "amend": amend,
      "branch": git.branch (),
      "branch_ref": branch_ref,
      "feature_id": feature.get ("feature_id") if feature else None,
      "groups": groups,
      "head_oid": head,
      "parent_oid": git.parent ("HEAD") if amend else head,
      "changes": changes,
      "desired_tree": desired_tree,
      "mode": mode,
      "paths": paths,
      "preserved_index": [
         { "entry": git.index_entry (path), "path": path }
         for path in staged_paths
         if path not in paths
      ],
   }
   items = [
      {
         "action": "commit",
         "message": group ["message"],
         "paths": group ["files"],
         "changes": group ["changes"],
      }
      for group in groups
   ]
   return plans.create (
      "commit",
      label,
      scope={ "branch": git.branch (), "feature_id": payload ["feature_id"], "mode": mode },
      items=items,
      fingerprint=fingerprint.repository (),
      payload_schema="imp.commit-plan.v2",
      payload=payload,
      warnings=warnings,
      persist=persist,
   )


def _apply_payload (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   if plan.get ("payload_schema") != "imp.commit-plan.v2":
      raise state.StateError ("Commit plan uses an older format; create a new plan")
   if fingerprint.repository () != plan.get ("fingerprint"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Commit plan is stale because repository state changed")

   payload = dict (plan ["payload"])
   if payload.get ("actor_id") != actor_id:
      raise state.StateError (f"Commit plan belongs to {payload.get ('actor_id')}")
   if git.current_ref () != payload.get ("branch_ref") or git.rev_parse ("HEAD") != payload.get ("head_oid"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Commit plan branch or HEAD changed")

   max_subject = int (repo.get ("commit:max_subject", 72))
   messages = (str (group.get ("message", "")) for group in payload ["groups"])
   if any (not validate.commit (message, max_subject) for message in messages):
      raise state.StateError ("Commit plan contains an invalid message")
   features.assert_write_access (actor_id)
   return payload


def _build_commits (payload: dict [str, Any], index) -> tuple [str, list [dict [str, Any]]]:
   commits = []
   head = str (payload ["head_oid"])
   parent = str (payload.get ("parent_oid", head))
   if head:
      git.index_read_tree (index, head)
   else:
      git.index_read_empty (index)
   for group in payload ["groups"]:
      patches.apply (index, list (payload ["changes"]), list (group ["changes"]))
      tree = git.index_write_tree (index)
      head = git.commit_tree (tree, parent, str (group ["message"]))
      parent = head
      commits.append ({ "oid": head, "message": group ["message"], "paths": group ["files"] })
   if payload ["desired_tree"] != git.index_write_tree (index):
      raise state.StateError ("Commit chain does not cover the exact selected tree")
   return head, commits


def _restore_ref (payload: dict [str, Any], head: str, backup, real_index):
   previous = str (payload ["head_oid"])
   try:
      if previous:
         git.update_ref_checked (str (payload ["branch_ref"]), previous, head)
      else:
         git.delete_ref_checked (str (payload ["branch_ref"]), head)
   finally:
      if backup.exists ():
         backup.replace (real_index)


def _move_ref (payload: dict [str, Any], head: str, backup):
   real_index = git.index_path ()
   if real_index.exists ():
      shutil.copy2 (real_index, backup)
   git.update_ref_checked (str (payload ["branch_ref"]), head, str (payload ["head_oid"]))
   try:
      git.reset_mixed (head)
      for preserved in payload.get ("preserved_index", []):
         entry = preserved.get ("entry")
         git.index_set_current (str (preserved ["path"]), tuple (entry) if entry else None)
   except Exception:
      _restore_ref (payload, head, backup, real_index)
      raise


def _apply_commits (plan: dict [str, Any], payload: dict [str, Any]) -> list [dict [str, Any]]:
   index = state.temporary ("commit-index-")
   backup = state.temporary ("real-index-")
   try:
      head, commits = _build_commits (payload, index)
      if fingerprint.repository () != plan.get ("fingerprint"):
         raise state.StateError ("Repository state changed while commits were prepared")
      _move_ref (payload, head, backup)
      return commits
   except Exception as error:
      if fingerprint.repository () != plan.get ("fingerprint"):
         plans.mark (plan, "stale", stale_at=state.now ())
      else:
         plans.mark (plan, "failed", failed_at=state.now (), error=str (error))
      raise
   finally:
      index.unlink (missing_ok=True)
      backup.unlink (missing_ok=True)


def apply (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   """Build every commit off-ref, then atomically move the current branch."""

   payload = _apply_payload (plan, actor_id)
   with state.lock (f"commit-{identity.slug (str (payload ['branch']))}"):
      commits = _apply_commits (plan, payload)

   plans.mark (plan, "applied", applied_at=state.now (), commit_oids=[commit ["oid"] for commit in commits])
   return {
      "branch": payload ["branch"],
      "commits": commits,
      "feature_id": payload ["feature_id"],
      "plan_id": plan ["plan_id"],
   }
