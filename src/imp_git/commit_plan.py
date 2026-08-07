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


def _groups (
   changes: list [dict [str, str]],
   whisper: str,
   single: bool,
) -> list [dict [str, Any]]:
   diffs = patches.content (changes)
   branch = git.branch ()
   hunk_ids = [change ["hunk_id"] for change in changes]
   if single or len (changes) == 1:
      message = ai.commit_message (prompts.commit (diffs, branch, whisper))
      return [ {
         "message": message,
         "files": sorted ({ change ["path"] for change in changes }),
         "hunks": hunk_ids,
      } ]

   response = ai.strip_fences (ai.smart (prompts.split_hunks (diffs, len (changes), branch, whisper)))
   try:
      groups = json.loads (response)
   except json.JSONDecodeError as error:
      raise state.StateError ("AI returned an invalid commit plan") from error
   if not isinstance (groups, list) or not groups:
      raise state.StateError ("AI returned an empty commit plan")

   covered: list [str] = []
   normalized = []
   by_id = { change ["hunk_id"]: change for change in changes }
   for group in groups:
      if not isinstance (group, dict):
         raise state.StateError ("AI commit groups must be objects")
      message = str (group.get ("message", ""))
      hunks = group.get ("hunks", [])
      if not validate.commit (message, int (repo.get ("commit:max_subject", 72))):
         raise state.StateError (f"Invalid Conventional Commit message: {message}")
      if not isinstance (hunks, list) or not all (isinstance (hunk, str) for hunk in hunks):
         raise state.StateError ("AI commit groups require hunk lists")
      if not hunks:
         raise state.StateError ("AI commit groups cannot be empty")
      covered.extend (hunks)
      normalized.append ({
         "message": message,
         "files": sorted ({ by_id [hunk] ["path"] for hunk in hunks if hunk in by_id }),
         "hunks": hunks,
      })

   if len (covered) != len (set (covered)):
      raise state.StateError ("AI assigned a path to more than one commit")
   if set (covered) != set (hunk_ids):
      raise state.StateError ("AI commit groups do not cover every selected hunk")

   return normalized


def groups_for_paths (paths: list [str], *, staged: bool = False, whisper: str = "") -> list [dict [str, Any]]:
   """Propose logical groups without creating a commit plan."""

   mode = "staged" if staged else "all"
   changes, _tree = patches.changes (paths, mode)
   return _groups (changes, whisper, single=False)


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
   if not paths:
      raise state.StateError ("Nothing selected to commit")

   warnings, blockers = hygiene.inspect (paths)
   if blockers:
      changes: list [dict [str, str]] = []
      desired_tree = ""
      groups = []
   else:
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
         "hunks": group ["hunks"],
      }
      for group in groups
   ]
   return plans.create (
      "commit",
      label,
      scope={ "branch": git.branch (), "feature_id": payload ["feature_id"], "mode": mode },
      items=items,
      fingerprint=fingerprint.repository (),
      payload_schema="imp.commit-plan.v1",
      payload=payload,
      warnings=warnings,
      blockers=blockers,
      persist=persist,
   )


def apply (plan: dict [str, Any], actor_id: str) -> dict [str, Any]:
   """Build every commit off-ref, then atomically move the current branch."""

   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   if plan.get ("payload_schema") != "imp.commit-plan.v1":
      raise state.StateError ("Unsupported commit plan payload")
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
   index = state.temporary ("commit-index-")
   commits = []
   head = str (payload ["head_oid"])
   parent = str (payload.get ("parent_oid", head))
   branch_ref = str (payload ["branch_ref"])
   updated_ref = False
   backup = state.temporary ("real-index-")

   with state.lock (f"commit-{identity.slug (str (payload ['branch']))}"):
      try:
         if head:
            git.index_read_tree (index, head)
         else:
            git.index_read_empty (index)
         for group in payload ["groups"]:
            patches.apply (index, list (payload ["changes"]), list (group ["hunks"]))
            tree = git.index_write_tree (index)
            head = git.commit_tree (tree, parent, str (group ["message"]))
            parent = head
            commits.append ({ "oid": head, "message": group ["message"], "paths": group ["files"] })

         if payload ["desired_tree"] != git.index_write_tree (index):
            raise state.StateError ("Commit chain does not cover the exact selected tree")

         if fingerprint.repository () != plan.get ("fingerprint"):
            plans.mark (plan, "stale", stale_at=state.now ())
            raise state.StateError ("Repository state changed while commits were prepared")

         real_index = git.index_path ()
         if real_index.exists ():
            shutil.copy2 (real_index, backup)
         git.update_ref_checked (branch_ref, head, str (payload ["head_oid"]))
         updated_ref = True
         try:
            git.reset_mixed (head)
            for preserved in payload.get ("preserved_index", []):
               entry = preserved.get ("entry")
               normalized = tuple (entry) if entry else None
               git.index_set_current (str (preserved ["path"]), normalized)
         except Exception:
            try:
               previous = str (payload ["head_oid"])
               if previous:
                  git.update_ref_checked (branch_ref, previous, head)
               else:
                  git.delete_ref_checked (branch_ref, head)
            finally:
               if backup.exists ():
                  backup.replace (real_index)
               updated_ref = False
            raise
      except Exception as error:
         if not updated_ref:
            plans.mark (plan, "failed", failed_at=state.now (), error=str (error))
         raise
      finally:
         index.unlink (missing_ok=True)
         backup.unlink (missing_ok=True)

   plans.mark (plan, "applied", applied_at=state.now (), commit_oids=[commit ["oid"] for commit in commits])
   return {
      "branch": payload ["branch"],
      "commits": commits,
      "feature_id": payload ["feature_id"],
      "plan_id": plan ["plan_id"],
   }
