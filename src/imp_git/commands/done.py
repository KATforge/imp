from pathlib import Path
from typing import Annotated

import typer

from imp_git import approval, console, features, git, integration, plans, roster, runtime, state, workspace


def _feature (value: str) -> dict:
   return features.resolve (
      value,
      states={ "active", "awaiting-merge" },
      title="Select feature to complete",
   )


def _show_diff (value: str):
   if not value:
      return
   console.divider ()
   console.out.print (value)
   console.divider ()


def _show (plan: dict):
   payload = plan ["payload"]
   console.header ("Complete feature")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Feature", str (plan ["label"]) ],
         [ "Target", str (payload ["target_ref"]) ],
         [ "Candidate", str (payload ["candidate_oid"]) [:12] ],
      ],
   )
   for blocker in plan ["blockers"]:
      console.err (str (blocker))
   _show_diff (str (payload ["diff"]))


def done (
   feature: Annotated [str, typer.Argument (help="Feature name")] = "",
   all_features: Annotated [bool, typer.Option ("--all", help="Integrate every open feature")] = False,
):
   """Integrate one or all exact feature candidates into trunk."""

   inside = git.succeeds ("rev-parse", "--git-dir")
   notes = _standing_here () if inside else []
   if all_features:
      if feature:
         console.fatal ("Pass a feature or --all, not both")
      return _promote (_all (), warnings=notes)
   group = _group (feature)
   if not group and not inside:
      git.require ()
   if group:
      return _promote (group, warnings=notes)
   try:
      plan = integration.plan_done (_feature (feature))
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      command="imp done",
      noun="completion",
      confirm="Integrate this exact candidate?",
      plan_schema="imp.done-plan.v2",
      result_schema="imp.done.v2",
      apply=integration.apply_done,
      show=_show,
      success=lambda data: console.success ("Feature completed"),
      dry_run=runtime.options.dry_run,
      yes=runtime.options.yes,
      json_output=runtime.options.json,
      warnings=notes,
   )


def _standing_here () -> list [str]:
   try:
      here = Path.cwd ().resolve ()
   except OSError:
      return []
   for feature in features.eligible ({ "active", "awaiting-merge" }, live=False):
      path = Path (str (feature ["path"])).resolve ()
      if here == path or path in here.parents:
         return [ f"You are standing in {path}, which this removes; run from the repository root" ]
   return []


def _entry_group (value: dict, entry: dict) -> dict:
   return {
      "name": str (entry ["name"]),
      "members": roster.ordered_members (entry),
      "workspace": value,
   }


def _group (feature: str) -> dict | None:
   value = workspace.here ()
   if not value:
      return None
   inside = git.succeeds ("rev-parse", "--git-dir")
   if not feature:
      return None if inside else _pick (value)
   entry = next ((row for row in roster.collect (value) if row ["name"] == feature), None)
   if not entry or (inside and len (entry ["members"]) < 2):
      return None
   return _entry_group (value, entry)


def _pick (value: dict) -> dict:
   entries = roster.collect (value)
   if not entries:
      console.fatal (f"No open features in {value ['name']}")
   if runtime.options.json or runtime.options.no_input:
      console.fatal ("Pass an explicit feature name")
   labels = {
      f"{entry ['name']}   {' '.join (entry ['repositories'])}   {entry ['age']}": entry
      for entry in entries
   }
   return _entry_group (value, labels [console.choose ("Select a feature", list (labels))])


def _all () -> dict:
   value = workspace.here ()
   entries = roster.collect (value) if value else []
   if not entries:
      console.fatal ("No open features")
   return {
      "groups": [ _entry_group (value, entry) for entry in entries ],
      "name": "all features",
      "workspace": value,
   }


def _show_group (plan: dict):
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


def _member_label (entry: dict, member: dict, all_features: bool) -> str:
   if not all_features:
      return str (member ["alias"])
   if len (entry ["members"]) == 1:
      return str (entry ["name"])
   return f"{entry ['name']}/{member ['alias']}"


def _plan_group (group: dict) -> dict:
   children = []
   blockers = []
   groups = group.get ("groups") or [ group ]
   all_features = "groups" in group
   targets = {}
   for entry in groups:
      for member in entry ["members"]:
         with workspace.inside (member ["repository"]):
            feature = features.resolve (
               str (member ["feature_id"]), states={ "active", "awaiting-merge" }, title="Select feature",
            )
            target = str (feature.get ("target") or git.base_branch ())
            key = (str (member ["repository"]), target)
            resolved = targets.get (key) or integration.target_state (target)
            child = integration.plan_done (feature, resolved_target=resolved)
         payload = child ["payload"]
         targets [key] = (payload ["candidate_oid"], payload ["remote_target_oid"], payload ["candidate_oid"])
         label = _member_label (entry, member, all_features)
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
      str (group ["name"]),
      scope={ "workspace": str (group ["workspace"] ["name"]) },
      items=[
         {
            "action": "integrate",
            "alias": child ["alias"],
            "candidate": child ["plan"] ["payload"] ["candidate_oid"],
            "feature": child ["feature"],
         }
         for child in children
      ],
      payload_schema="imp.promote-plan.v2",
      payload={
         "all": all_features,
         "feature": str (group ["name"]),
         "features": [ str (entry ["name"]) for entry in groups ],
         "order": [ child ["label"] for child in children ],
         "members": children,
      },
      blockers=blockers,
   )


def _apply_group (plan: dict) -> dict:
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
      "completed": plan ["payload"] ["features"] if plan ["payload"] ["all"] else landed,
      "feature": plan ["payload"] ["feature"],
      "order": plan ["payload"] ["order"],
   }


def _promote (group: dict, *, warnings: list [str]):
   try:
      plan = _plan_group (group)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      command="imp done",
      noun="integration",
      confirm="Integrate these exact candidates?",
      plan_schema="imp.promote-plan.v2",
      result_schema="imp.promote.v3",
      apply=_apply_group,
      show=_show_group,
      success=lambda data: console.success (
         f"Completed {len (data ['completed'])} features"
         if "groups" in group else f"Feature completed across {len (data ['completed'])} repositories"
      ),
      dry_run=runtime.options.dry_run,
      yes=runtime.options.yes,
      json_output=runtime.options.json,
      warnings=warnings,
   )
