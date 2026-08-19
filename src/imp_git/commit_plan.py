import shutil
from pathlib import Path
from typing import Any

from imp_git import ai, features, fingerprint, git, hygiene, identity, locks, plans, prompts, state, validate


def _trunk_claim () -> str:
   """Return the trunk branch when committing directly on it in the primary checkout."""

   branch = git.branch ()
   if not branch or branch != git.base_branch ():
      return ""
   entries = git.worktrees ()
   if not entries:
      return branch
   primary = str (Path (entries [0].get ("worktree", "")).resolve ())
   return branch if primary == str (Path (git.repo_root ()).resolve ()) else ""


def _scope () -> tuple [str, list [str]]:
   staged = git.changed_paths (staged=True)
   return ("staged", staged) if staged else ("all", git.changed_paths (all_changes=True))


def _candidate (paths: list [str], mode: str) -> tuple [str, str]:
   index = state.temporary ("commit-index-")
   try:
      git.index_read_tree (index, "HEAD") if git.ref_exists ("HEAD") else git.index_read_empty (index)
      if mode == "all":
         git.index_add_worktree (index, paths)
      else:
         for path in paths:
            git.index_set (index, path, git.index_entry (path))
      return git.index_write_tree (index), git.index_diff (index)
   finally:
      index.unlink (missing_ok=True)


def create (*, message: str = "") -> dict [str, Any]:
   mode, selected = _scope ()
   staged = git.changed_paths (staged=True)
   paths = git.committable_paths (selected)
   if not paths:
      raise state.StateError ("Nothing selected to commit")
   tree, diff = _candidate (paths, mode)
   feature = features.current ()
   branch = git.branch ()
   branch_ref = git.current_ref ()
   if not branch_ref:
      raise state.StateError ("Commit planning requires an attached branch")
   trunk_claim = _trunk_claim ()
   ticket = str (feature ["ticket"]) if feature else ""
   if trunk_claim:
      taken = locks.foreign (trunk_claim)
      if taken:
         raise state.StateError (
            f"{trunk_claim} is locked by {taken ['actor']} ({taken ['name']}); imp start to get a worktree"
         )
      held = locks.holder (trunk_claim)
      if held:
         ticket = held ["ticket"]
   if message:
      if not validate.commit (message):
         raise state.StateError ("Message must use Conventional Commits")
   else:
      message = ai.commit_message (prompts.commit (ai.truncate (diff), branch, ticket))
   payload = {
      "branch": branch,
      "branch_ref": branch_ref,
      "feature": feature ["branch"] if feature else None,
      "head_oid": git.rev_parse ("HEAD"),
      "message": message,
      "mode": mode,
      "paths": paths,
      "preserved_index": [
         { "entry": git.index_entry (path), "path": path }
         for path in staged
         if path not in paths
      ],
      "tree_oid": tree,
      "trunk_claim": trunk_claim,
   }
   return plans.build (
      "commit",
      str (feature ["name"]) if feature else identity.slug (branch or "detached"),
      scope={ "branch": branch, "feature": payload ["feature"], "mode": mode },
      items=[ { "action": "commit", "message": message, "paths": paths } ],
      fingerprint=fingerprint.repository (),
      payload_schema="imp.commit-plan.v4",
      payload=payload,
      warnings=hygiene.inspect (paths),
   )


def _payload (plan: dict [str, Any]) -> dict [str, Any]:
   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   if plan.get ("payload_schema") != "imp.commit-plan.v4":
      raise state.StateError ("Commit plan uses an older format; create a new plan")
   if fingerprint.repository () != plan.get ("fingerprint"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Commit plan is stale because repository state changed")
   payload = dict (plan ["payload"])
   if git.current_ref () != payload ["branch_ref"] or git.rev_parse ("HEAD") != payload ["head_oid"]:
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Commit plan branch or HEAD changed")
   if not validate.commit (str (payload ["message"])):
      raise state.StateError ("Commit plan contains an invalid message")
   if payload.get ("trunk_claim"):
      locks.acquire (str (payload ["trunk_claim"]))
   return payload


def _restore (payload: dict [str, Any], candidate: str, backup, index):
   try:
      git.update_ref_checked (str (payload ["branch_ref"]), str (payload ["head_oid"]), candidate)
   finally:
      if backup.exists ():
         backup.replace (index)


def _move (payload: dict [str, Any], candidate: str, backup):
   index = git.index_path ()
   if index.exists ():
      shutil.copy2 (index, backup)
   git.update_ref_checked (str (payload ["branch_ref"]), candidate, str (payload ["head_oid"]))
   try:
      git.reset_mixed (candidate)
      for preserved in payload ["preserved_index"]:
         entry = preserved ["entry"]
         git.index_set_current (str (preserved ["path"]), tuple (entry) if entry else None)
   except Exception:
      _restore (payload, candidate, backup, index)
      raise


def apply (plan: dict [str, Any]) -> dict [str, Any]:
   payload = _payload (plan)
   backup = state.temporary ("real-index-")
   try:
      candidate = git.commit_tree (
         str (payload ["tree_oid"]), str (payload ["head_oid"]), str (payload ["message"]),
      )
      if fingerprint.repository () != plan ["fingerprint"]:
         raise state.StateError ("Repository state changed while the commit was prepared")
      _move (payload, candidate, backup)
   except Exception as error:
      value = "stale" if fingerprint.repository () != plan ["fingerprint"] else "failed"
      plans.mark (plan, value, failed_at=state.now (), error=str (error))
      raise
   finally:
      backup.unlink (missing_ok=True)
   commit = { "oid": candidate, "message": payload ["message"], "paths": payload ["paths"] }
   plans.mark (plan, "applied", applied_at=state.now (), commit_oids=[ candidate ])
   return { "branch": payload ["branch"], "commits": [ commit ], "feature": payload ["feature"] }
