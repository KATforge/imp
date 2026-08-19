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
):
   """Integrate one exact candidate into trunk."""

   inside = git.succeeds ("rev-parse", "--git-dir")
   notes = _standing_here () if inside else []
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


def _show_group (plan: dict):
   console.header (f"Complete feature: {plan ['label']}")
   console.table (
      [ "Repository", "Candidate" ],
      [
         [ str (member ["alias"]), str (member ["plan"] ["payload"] ["candidate_oid"]) [:12] ]
         for member in plan ["payload"] ["members"]
      ],
   )
   for blocker in plan ["blockers"]:
      console.err (str (blocker))
   for member in plan ["payload"] ["members"]:
      diff = str (member ["plan"] ["payload"] ["diff"])
      if diff:
         console.label (str (member ["alias"]))
         _show_diff (diff)


def _plan_group (group: dict) -> dict:
   children = []
   blockers = []
   for member in group ["members"]:
      with workspace.inside (member ["repository"]):
         child = integration.plan_done (features.resolve (
            str (group ["name"]), states={ "active", "awaiting-merge" }, title="Select feature",
         ))
      blockers.extend (f"{member ['alias']}: {reason}" for reason in child ["blockers"])
      children.append ({ "alias": member ["alias"], "repository": member ["repository"], "plan": child })
   return plans.build (
      "done",
      str (group ["name"]),
      scope={ "feature": str (group ["name"]), "workspace": str (group ["workspace"] ["name"]) },
      items=[
         {
            "action": "integrate",
            "alias": child ["alias"],
            "candidate": child ["plan"] ["payload"] ["candidate_oid"],
         }
         for child in children
      ],
      payload_schema="imp.promote-plan.v2",
      payload={
         "feature": str (group ["name"]),
         "order": [ child ["alias"] for child in children ],
         "members": children,
      },
      blockers=blockers,
   )


def _apply_group (plan: dict) -> dict:
   completed = []
   for child in plan ["payload"] ["members"]:
      try:
         with workspace.inside (child ["repository"]):
            integration.apply_done (child ["plan"])
      except (state.StateError, ValueError) as error:
         landed = ", ".join (completed) or "nothing"
         raise state.StateError (f"{child ['alias']} failed after integrating {landed}: {error}") from error
      completed.append (str (child ["alias"]))
   return {
      "completed": completed,
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
         f"Feature completed across {len (data ['completed'])} repositories"
      ),
      dry_run=runtime.options.dry_run,
      yes=runtime.options.yes,
      json_output=runtime.options.json,
      warnings=warnings,
   )
