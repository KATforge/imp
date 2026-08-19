from pathlib import Path
from typing import Annotated, Any

import typer

from imp_git import approval, console, features, git, plans, state

_MARK = "imp done: "


def _layer (trunk: str) -> tuple [str, str, str]:
   """Find the newest integrated layer in trunk's reflog: branch, its head, and the state before it."""

   entries = git.reflog_entries (f"refs/heads/{trunk}")
   index = next (
      (position for position, entry in enumerate (entries) if entry ["subject"].startswith (_MARK)),
      None,
   )
   if index is None:
      raise state.StateError (f"No imp done layer in the {trunk} reflog")
   if index + 1 >= len (entries):
      raise state.StateError ("Reflog does not record the pre-integration state")
   entry = entries [index]
   return entry ["subject"].removeprefix (_MARK), entry ["oid"], entries [index + 1] ["oid"]


def _plan (trunk: str, feature: str) -> dict [str, Any]:
   branch, new_oid, old_oid = _layer (trunk)
   if feature and features.name_of (feature) != features.name_of (branch) and feature != branch:
      raise state.StateError (
         f"The last layer on {trunk} is {branch}; only the most recent layer can be undone"
      )
   blockers = []
   if git.rev_parse (trunk) != new_oid:
      blockers.append (f"{trunk} moved after this layer; back the newer work out first")
   if git.remote_exists ():
      git.fetch (remote="origin", refspec=f"+refs/heads/{trunk}:refs/remotes/origin/{trunk}")
      remote_oid = git.rev_parse (f"origin/{trunk}")
      if remote_oid and git.is_merged (new_oid, remote_oid):
         blockers.append (f"Layer is already pushed to origin/{trunk}; revert it on trunk instead")
   if git.ref_exists (branch):
      blockers.append (f"Branch already exists: {branch}")
   for path in git.ref_worktrees (trunk):
      if not git.clean_at (path):
         blockers.append (f"Trunk worktree is dirty: {path}")
   payload = {
      "branch": branch,
      "commits": git.log_oneline (rev_range=f"{old_oid}..{new_oid}"),
      "new_oid": new_oid,
      "old_oid": old_oid,
      "trunk": trunk,
   }
   return plans.build (
      "undo",
      features.name_of (branch),
      scope={ "repository": git.repo_name (), "trunk": trunk },
      items=[
         { "action": "reset", "ref": trunk, "to": old_oid },
         { "action": "restore_branch", "branch": branch, "at": new_oid },
      ],
      payload_schema="imp.undo-plan.v1",
      payload=payload,
      blockers=blockers,
   )


def _apply (plan: dict [str, Any]) -> dict [str, Any]:
   payload = plan ["payload"]
   trunk = str (payload ["trunk"])
   branch = str (payload ["branch"])
   git.update_ref_checked (
      f"refs/heads/{trunk}", str (payload ["old_oid"]), str (payload ["new_oid"]),
      message=f"imp undo: {branch}",
   )
   for path in git.ref_worktrees (trunk):
      git.reset_at (path, str (payload ["old_oid"]))
   git.update_ref_checked (f"refs/heads/{branch}", str (payload ["new_oid"]), "")
   path = str (features.worktree_path (features.name_of (branch)))
   restored = ""
   if not Path (path).exists ():
      git.worktree_add_existing (path, branch)
      restored = path
   plans.mark (plan, "applied", applied_at=state.now ())
   return {
      "branch": branch,
      "path": restored,
      "trunk": trunk,
      "trunk_oid": payload ["old_oid"],
   }


def _show (plan: dict [str, Any]):
   payload = plan ["payload"]
   console.header (f"Undo layer: {plan ['label']}")
   console.table ([ "Field", "Value" ], [
      [ "Trunk", f"{payload ['trunk']} → {str (payload ['old_oid']) [:12]}" ],
      [ "Restore", f"{payload ['branch']} at {str (payload ['new_oid']) [:12]}" ],
   ])
   console.items ("Commits backed out", str (payload ["commits"]))
   for blocker in plan ["blockers"]:
      console.err (str (blocker))


def undo (
   feature: Annotated [
      str,
      typer.Argument (help="Feature the top layer must match; omit to undo whatever landed last"),
   ] = "",
):
   """Back the most recent integrated layer off trunk and restore it as a feature.

   Reads trunk's reflog for the newest `imp done` stamp, moves trunk back to the state
   just before it by compare-and-swap, and recreates the feature branch and worktree at
   the layer's head, so nothing is lost and the work can be fixed and reintegrated.

   Only the top unpushed layer can be undone: if trunk moved afterwards, back the newer
   work out first, and once a layer is pushed it must be reverted instead. Deterministic;
   sends nothing to AI.
   """

   git.require ()
   try:
      plan = _plan (git.base_branch (), feature)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      noun="undo",
      confirm="Back this layer out of trunk?",
      result_schema="imp.undo.v1",
      apply=_apply,
      show=_show,
      success=lambda data: console.success (
         f"Backed out {data ['branch']}; restored at {data ['path'] or 'existing worktree'}"
      ),
      destructive=True,
   )
