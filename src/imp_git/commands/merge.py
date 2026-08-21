from pathlib import Path
from typing import Annotated, Any

import typer

from imp_git import (
   approval,
   console,
   features,
   git,
   identity,
   integration,
   layers,
   locks,
   plans,
   result,
   roster,
   runtime,
   state,
   workspace,
)


def _show_diff (value: str):
   if not value:
      return
   console.divider ()
   console.raw (value)
   console.divider ()


def _standing (entries: list [dict [str, Any]]) -> list [str]:
   try:
      here = Path.cwd ().resolve ()
   except OSError:
      return []
   for entry in entries:
      for member in entry ["members"]:
         if not member ["path"]:
            continue
         path = Path (str (member ["path"])).resolve ()
         if here == path or path in here.parents:
            return [ f"You are standing in {path}, which this removes; run from the repository root" ]
   return []


def _select (entries: list [dict [str, Any]], feature: str, all_features: bool) -> list [dict [str, Any]]:
   if all_features or not entries:
      return entries
   if feature:
      wanted = features.name_of (feature)
      return [
         entry for entry in entries
         if entry ["name"] == wanted or any (member ["branch"] == feature for member in entry ["members"])
      ]
   if len (entries) == 1:
      return entries
   if runtime.options.json or runtime.options.no_input:
      console.fatal ("Pass an explicit feature name or --all")
   labels = {
      f"{entry ['name']}   {' '.join (entry ['repositories'])}   {entry ['age']}": entry
      for entry in entries
   }
   return [ labels [console.choose ("Select a feature", list (labels))] ]


def _my_locks (value: dict [str, Any], feature: str) -> list [tuple [str, str, dict [str, str]]]:
   """Find trunk locks held by this actor, optionally matching one requested name."""

   held = []
   wanted = identity.slug (feature) if feature else ""
   for _alias, repository in sorted (workspace.repositories (value).items ()):
      with workspace.inside (repository):
         trunk = git.base_branch ()
         lock = locks.holder (trunk)
      if not lock or lock ["actor"] != identity.actor ():
         continue
      if wanted and lock ["name"] != wanted:
         continue
      held.append ((repository, trunk, lock))
   return held


def _release (value: dict [str, Any], feature: str) -> dict [str, Any] | None:
   """Release this actor's trunk locks, recording each session as one undoable layer."""

   held = _my_locks (value, feature)
   if not held:
      return None
   released = []
   for repository, trunk, lock in held:
      with workspace.inside (repository):
         for path in git.ref_worktrees (trunk):
            if not git.clean_at (path):
               console.fatal (
                  f"{trunk} has uncommitted session work; imp commit or discard it before imp done"
               )
         bare = features.branch_for (lock ["name"], lock ["ticket"]).removeprefix (features.PREFIX)
         layers.record (bare, git.rev_parse (trunk), lock ["base"])
         locks.release (trunk)
      released.append (trunk)
   data = {
      "completed": [],
      "feature": feature or held [0] [2] ["name"],
      "order": [],
      "released": released,
   }
   if runtime.options.json:
      return result.emit ("imp.done.v3", "imp done", data, json_output=True)
   console.success (f"Trunk released: {', '.join (released)}")
   return data


def _plan_group (name: str, workspace_name: str, entries: list [dict [str, Any]]) -> dict [str, Any]:
   children = []
   blockers = []
   batch = len (entries) > 1
   targets: dict [tuple [str, str], tuple [str, str, str]] = {}
   for entry in entries:
      for member in entry ["members"]:
         with workspace.inside (member ["repository"]):
            feature = features.resolve (str (member ["branch"]))
            target = str (feature ["target"])
            key = (str (member ["repository"]), target)
            resolved = targets.get (key) or integration.target_state (target)
            child = integration.plan_done (feature, resolved_target=resolved)
         payload = child ["payload"]
         targets [key] = (payload ["candidate_oid"], payload ["remote_target_oid"], payload ["candidate_oid"])
         label = f"{entry ['name']}/{member ['alias']}" if batch else str (member ["alias"])
         blockers.extend (f"{label}: {reason}" for reason in child ["blockers"])
         children.append ({
            "alias": member ["alias"],
            "feature": entry ["name"],
            "label": label,
            "repository": member ["repository"],
            "plan": child,
         })
   return plans.build (
      "done",
      name,
      scope={ "workspace": workspace_name },
      items=[
         {
            "action": "integrate",
            "alias": child ["alias"],
            "candidate": child ["plan"] ["payload"] ["candidate_oid"],
            "feature": child ["feature"],
         }
         for child in children
      ],
      payload_schema="imp.done-plan.v4",
      payload={
         "feature": name,
         "features": [ str (entry ["name"]) for entry in entries ],
         "order": [ child ["label"] for child in children ],
         "members": children,
      },
      blockers=blockers,
   )


def _apply_group (plan: dict [str, Any]) -> dict [str, Any]:
   landed = []
   for child in plan ["payload"] ["members"]:
      try:
         with workspace.inside (child ["repository"]):
            integration.apply_done (child ["plan"])
      except (state.StateError, ValueError) as error:
         detail = ", ".join (landed) or "nothing"
         raise state.StateError (f"{child ['label']} failed after integrating {detail}: {error}") from error
      landed.append (str (child ["label"]))
   return {
      "completed": plan ["payload"] ["features"],
      "feature": plan ["payload"] ["feature"],
      "order": plan ["payload"] ["order"],
   }


def _show_group (plan: dict [str, Any]):
   console.header (f"Complete feature: {plan ['label']}")
   console.table (
      [ "Feature", "Repository", "Target", "Candidate" ],
      [
         [
            str (member ["feature"]),
            str (member ["alias"]),
            str (member ["plan"] ["payload"] ["target_ref"]),
            str (member ["plan"] ["payload"] ["candidate_oid"]) [:12],
         ]
         for member in plan ["payload"] ["members"]
      ],
   )
   for blocker in plan ["blockers"]:
      console.err (str (blocker))
   for member in plan ["payload"] ["members"]:
      diff = str (member ["plan"] ["payload"] ["diff"])
      if diff:
         console.label (str (member ["label"]))
         _show_diff (diff)


def done (
   feature: Annotated [str, typer.Argument (help="Feature name or branch; omit to pick the open one")] = "",
   all_features: Annotated [
      bool,
      typer.Option ("--all", help="Integrate every open feature, oldest first, as one exact batch"),
   ] = False,
):
   """Integrate a feature into trunk exactly as shown, then remove its branch and worktree.

   Builds the exact candidate off-ref (rebasing unpublished commits onto trunk, merging
   otherwise), runs the project's checks against it in a throwaway worktree, shows the
   complete diff, then moves trunk by compare-and-swap. The move is stamped in trunk's
   reflog, so `imp undo` can back the layer out later.

   A feature spanning repositories integrates dependency-first in its recorded span
   order and refuses as a whole if any member is blocked. With exactly one open
   feature, the name may be omitted.

   For trunk-mode work (started when the trunk lock was free), there is nothing to
   integrate: `imp done` releases the lock and records the session as one undoable
   layer. Bare `imp done` finishes your own trunk session first; name a feature to
   integrate one instead.

   Checks come from `git config imp.check` entries, or are detected from the project
   (package.json, composer.json, pyproject with pytest, Makefile). Deterministic;
   sends nothing to AI.
   """

   value = workspace.here ()
   if not value:
      console.fatal ("No repository here")
   if all_features and feature:
      console.fatal ("Pass a feature or --all, not both")
   if not all_features and not feature:
      released = _release (value, "")
      if released is not None:
         return released
   entries = roster.collect (value)
   selected = _select (entries, feature, all_features)
   if not selected:
      released = _release (value, feature)
      if released is not None:
         return released
      console.fatal (f"Unknown feature: {feature}" if feature else "No open features")
   notes = _standing (selected)
   name = "all features" if all_features else str (selected [0] ["name"])
   try:
      plan = _plan_group (name, str (value ["name"]), selected)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      noun="integration",
      confirm="Integrate these exact candidates?",
      result_schema="imp.done.v3",
      apply=_apply_group,
      show=_show_group,
      success=lambda data: console.success (
         f"Completed {len (data ['completed'])} features"
         if all_features else f"Feature completed: {data ['feature']}"
      ),
      warnings=notes,
   )
