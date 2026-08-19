from pathlib import Path
from typing import Annotated, Any

import typer

from imp_git import approval, console, features, git, identity, layers, locks, plans, state


def _session (trunk: str, head: str) -> dict [str, Any] | None:
   """The live trunk session, when this actor holds the lock and has landed commits."""

   lock = locks.holder (trunk)
   if not lock or lock ["actor"] != identity.actor ():
      return None
   base = lock ["base"]
   if not base or base == head or not git.is_merged (base, head):
      return None
   bare = features.branch_for (lock ["name"], lock ["ticket"]).removeprefix (features.PREFIX)
   return { "bare": bare, "base": base, "head": head, "kind": "session", "root": "" }


def _target (trunk: str, feature: str) -> dict [str, Any]:
   head = git.rev_parse (trunk)
   layer = _session (trunk, head)
   if not layer:
      layer = layers.at_head (head)
      if layer:
         layer = { **layer, "kind": "layer" }
   if not layer:
      if layers.all ():
         raise state.StateError (f"{trunk} moved after the last layer; nothing safe to undo")
      raise state.StateError (f"No imp layers on {trunk} to undo")
   if feature and features.name_of (feature) not in (features.name_of (layer ["bare"]), layer ["bare"]):
      raise state.StateError (
         f"The top layer on {trunk} is {layer ['bare']}; only the most recent layer can be undone"
      )
   return layer


def _plan (trunk: str, feature: str) -> dict [str, Any]:
   layer = _target (trunk, feature)
   branch = f"{features.PREFIX}{layer ['bare']}"
   blockers = []
   if layer ["kind"] == "layer":
      taken = locks.foreign (trunk)
      if taken:
         blockers.append (f"{trunk} is locked by {taken ['actor']} ({taken ['name']}); wait or ask them")
   if git.remote_exists ():
      git.fetch (remote="origin", refspec=f"+refs/heads/{trunk}:refs/remotes/origin/{trunk}")
      remote_oid = git.rev_parse (f"origin/{trunk}")
      if remote_oid and git.is_merged (layer ["head"], remote_oid):
         blockers.append (f"Layer is already pushed to origin/{trunk}; revert it on trunk instead")
   if git.ref_exists (branch):
      blockers.append (f"Branch already exists: {branch}")
   for path in git.ref_worktrees (trunk):
      if not git.clean_at (path):
         blockers.append (f"Trunk worktree is dirty: {path}")
   payload = {
      "branch": branch,
      "commits": git.log_oneline (rev_range=f"{layer ['base']}..{layer ['head']}"),
      "kind": layer ["kind"],
      "new_oid": layer ["head"],
      "old_oid": layer ["base"],
      "root": layer ["root"],
      "trunk": trunk,
   }
   return plans.build (
      "undo",
      features.name_of (layer ["bare"]),
      scope={ "repository": git.repo_name (), "trunk": trunk },
      items=[
         { "action": "reset", "ref": trunk, "to": layer ["base"] },
         { "action": "restore_branch", "branch": branch, "at": layer ["head"] },
      ],
      payload_schema="imp.undo-plan.v2",
      payload=payload,
      blockers=blockers,
   )


def _apply (plan: dict [str, Any]) -> dict [str, Any]:
   payload = plan ["payload"]
   trunk = str (payload ["trunk"])
   branch = str (payload ["branch"])
   bare = branch.removeprefix (features.PREFIX)
   git.update_ref_checked (
      f"refs/heads/{trunk}", str (payload ["old_oid"]), str (payload ["new_oid"]),
      message=f"imp undo: {bare}",
   )
   for path in git.ref_worktrees (trunk):
      git.reset_at (path, str (payload ["old_oid"]))
   git.update_ref_checked (f"refs/heads/{branch}", str (payload ["new_oid"]), "")
   path = str (features.worktree_path (features.name_of (branch)))
   restored = ""
   if not Path (path).exists ():
      git.worktree_add_existing (path, branch)
      restored = path
   if payload ["kind"] == "session":
      locks.release (trunk)
   else:
      layers.consume ({ "root": payload ["root"], "head": payload ["new_oid"], "base": payload ["old_oid"] })
      lock = locks.holder (trunk)
      if lock and lock ["actor"] == identity.actor ():
         locks.release (trunk)
         locks.acquire (trunk, lock ["name"], lock ["ticket"])
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
      [ "Kind", "live trunk session" if payload ["kind"] == "session" else "integrated layer" ],
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
   """Back the most recent layer off trunk and restore it as a feature worktree.

   Every unit of work is one layer: a worktree feature integrated by `imp done`, or a
   direct trunk session under the trunk lock. Undo moves trunk back to the state just
   before the top layer by compare-and-swap and recreates the work as feature/<name>
   with a worktree, so nothing is lost — fix it and `imp done` it again. Undoing a
   live trunk session also releases the lock.

   Layers unwind newest-first, one at a time; run undo repeatedly to go deeper. A
   pushed layer must be reverted instead, and a trunk locked by someone else blocks.
   Layer records live under refs/imp/layer and expire after 30 days. Deterministic;
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
