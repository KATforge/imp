from pathlib import Path
from typing import Annotated

import typer

from imp_git import (
   approval,
   console,
   features,
   git,
   identity,
   integration,
   plans,
   result,
   roster,
   runtime,
   state,
   workspace,
)


def _feature (value: str) -> dict:
   return features.resolve (
      value,
      states={ "active", "awaiting-merge" },
      title="Select feature to complete",
   )


def _show (plan: dict):
   payload = plan ["payload"]
   console.header ("Complete feature")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Feature", str (plan ["label"]) ],
         [ "Target", str (payload ["target_ref"]) ],
         [ "Strategy", str (payload ["strategy"]) ],
         [ "Candidate", str (payload ["candidate_oid"]) [:12] ],
      ],
   )
   for blocker in plan.get ("blockers", []):
      console.err (str (blocker))


def done (
   feature: Annotated [str, typer.Argument (help="Feature name")] = "",
   into: Annotated [str, typer.Option ("--into", help="Integration target")] = "",
   strategy: Annotated [str, typer.Option ("--strategy", help="preserve, squash, or merge")] = "",
   resolve: Annotated [
      str,
      typer.Option ("--resolve", help="Resolve conflicts: ours, theirs, edit, ai, or ask"),
   ] = "",
   all_ready: Annotated [
      bool,
      typer.Option ("--all", help="Integrate every ready feature, one after another"),
   ] = False,
   keep: Annotated [bool, typer.Option ("--keep", help="Keep the feature worktree and branch")] = False,
   skip_checks: Annotated [bool, typer.Option ("--skip-checks", help="Explicitly bypass checks")] = False,
   approve: Annotated [
      bool,
      typer.Option ("--approve", help="Approve the exact candidate without review"),
   ] = False,
):
   """Validate and integrate exactly one managed feature."""

   inside = git.succeeds ("rev-parse", "--git-dir")
   notes = _standing_here () if inside and not keep else []

   actor_id = runtime.options.actor_id
   dry_run = runtime.options.dry_run
   json_output = runtime.options.json
   yes = runtime.options.yes

   actor = identity.actor (actor_id)

   if resolve and resolve not in { "ours", "theirs", "edit", "ai", "ask" }:
      console.fatal (f"Unsupported conflict resolution: {resolve}")
   resolution = "resolve" if resolve == "ai" else resolve
   if approve and dry_run:
      console.fatal ("--approve cannot be combined with --dry-run")

   if all_ready:
      return _promote_every (
         actor, yes=yes, dry_run=dry_run, approve=approve, skip_checks=skip_checks,
         strategy=strategy, resolve=resolution, warnings=notes,
      )

   group = _group (feature)
   if not group and not inside:
      git.require ()
   if group:
      return _promote (
         group, actor, yes=yes, dry_run=dry_run, approve=approve,
         skip_checks=skip_checks, strategy=strategy, resolve=resolution, warnings=notes,
      )

   try:
      selected = _feature (feature)
      plan = integration.plan_done (
         selected, actor_id=actor, into=into, keep=keep,
         skip_checks=skip_checks, strategy=strategy, resolve=resolution,
      )
      if approve:
         integration.waive_review (plan)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   return approval.run (
      plan,
      command="imp done",
      noun="completion",
      confirm="Apply this exact integration plan?",
      plan_schema="imp.done-plan.v1",
      result_schema="imp.done.v1",
      apply=lambda value: _apply_one (value, actor, approve=approve),
      show=_show,
      success=lambda data: console.success ("Feature completed"),
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
      warnings=notes,
   )


def _standing_here () -> list [str]:
   """Warn when the caller stands in a worktree this run will remove.

   Integration deletes the feature worktree, which leaves the calling shell in a
   directory that no longer exists. Imp itself steps out, but the shell cannot, so
   the next prompt reports a missing working directory as though something failed.
   """

   try:
      here = Path.cwd ().resolve ()
   except OSError:
      return []
   for feature in features.all ():
      if feature.get ("state") not in { "active", "awaiting-merge" }:
         continue
      path = Path (str (feature ["path"])).resolve ()
      if here == path or path in here.parents:
         return [ f"You are standing in {path}, which this removes; run from the repository root" ]

   return []


def _promote_every (
   actor: str,
   *,
   yes: bool,
   dry_run: bool,
   approve: bool,
   skip_checks: bool,
   strategy: str,
   resolve: str,
   warnings: list [str],
):
   """Integrate every ready feature in turn, approved once.

   Each feature still builds its own candidate against the trunk of the moment and
   lands before the next one starts, so this automates the loop rather than stacking
   unvalidated work into a single merge. The run stops at the first failure and says
   what landed, because continuing past one would bury it.
   """

   machine = runtime.options.json
   value = workspace.here ()
   if not value:
      console.fatal ("No repository here and none below this directory")

   entries = roster.collect (value)
   ready = roster.promotable (entries)
   skipped = [ entry for entry in entries if entry not in ready ]
   if not ready:
      console.fatal (f"Nothing is ready to integrate in {value ['name']}")

   if not machine:
      console.header (f"Integrate {len (ready)} feature(s) · {value ['name']}")
      console.table (
         [ "Feature", "Repositories", "Age" ],
         [ [ str (e ["name"]), " ".join (e ["repositories"]), str (e ["age"]) ] for e in ready ],
      )
      for entry in skipped:
         console.muted (f"  skipping {entry ['name']} ({entry ['condition']})")
      for note in warnings:
         console.warn (note)

   data = {
      "landed": [],
      "ready": [ str (entry ["name"]) for entry in ready ],
      "skipped": [ str (entry ["name"]) for entry in skipped ],
      "workspace": value ["name"],
   }
   if dry_run:
      result.emit ("imp.promote-all.v1", "imp done", data, json_output=machine, warnings=warnings)
      return data
   if runtime.options.no_input and not yes:
      console.fatal ("Non-interactive integration requires --yes")
   if not yes and not console.confirm (f"Integrate all {len (ready)} in this order?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   failure = ""
   for entry in ready:
      group = _entry_group (value, entry)
      try:
         plan = _plan_group (
            group, actor, approve=approve, skip_checks=skip_checks, strategy=strategy, resolve=resolve,
         )
         if plan ["state"] != "ready":
            raise state.StateError ("; ".join (plan ["blockers"]))
         _apply_group (plan, actor, approve=approve)
      except typer.Exit:
         if not machine:
            console.muted (f"Integrated {len (data ['landed'])} of {len (ready)}")
         raise
      except (state.StateError, ValueError) as error:
         failure = f"Stopped at {entry ['name']}: {error}"
         break
      data ["landed"].append (str (entry ["name"]))

   if failure:
      data ["error"] = failure
   if machine:
      result.emit ("imp.promote-all.v1", "imp done", data, json_output=True, ok=not failure, warnings=warnings)
   elif failure:
      console.err (failure)
      console.muted (f"Integrated {len (data ['landed'])} of {len (ready)}")
   else:
      console.success (f"Integrated {len (data ['landed'])} of {len (ready)}")
   if failure:
      raise typer.Exit (1)

   return data


def _entry_group (value: dict, entry: dict) -> dict:
   return {
      "name": str (entry ["name"]),
      "members": roster.ordered_members (entry),
      "workspace": value,
   }


def _group (feature: str) -> dict | None:
   """Resolve one feature to its members across the workspace, or None for a plain feature.

   A feature spans repositories when the same name is managed in more than one of
   them. Nothing is declared: membership is what the checkouts below here hold.
   """

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
   ready = roster.promotable (entries)
   if not ready:
      console.fatal (f"Nothing is ready to integrate in {value ['name']}")
   if runtime.options.json or runtime.options.no_input:
      console.fatal ("Pass an explicit feature name")
   labels = {
      f"{entry ['name']}   {' '.join (entry ['repositories'])}   {entry ['age']}": entry
      for entry in ready
   }
   console.header (f"Integrate · {value ['name']}")

   return _entry_group (value, labels [console.choose ("Select a feature", list (labels))])


def _show_group (plan: dict):
   console.header (f"Complete feature: {plan ['label']}")
   console.table (
      [ "Repository", "Strategy", "Candidate" ],
      [
         [
            str (member ["alias"]),
            str (member ["plan"] ["payload"] ["strategy"]),
            str (member ["plan"] ["payload"] ["candidate_oid"]) [:12],
         ]
         for member in plan ["payload"] ["members"]
      ],
   )
   for blocker in plan.get ("blockers", []):
      console.err (str (blocker))


def _plan_group (
   group: dict,
   actor: str,
   *,
   approve: bool,
   skip_checks: bool,
   strategy: str,
   resolve: str,
) -> dict:
   """Plan every member of one feature in the order its span named."""

   children = []
   blockers = []
   for member in group ["members"]:
      with workspace.inside (member ["repository"]):
         selected = features.resolve (
            str (group ["name"]), states={ "active", "awaiting-merge" }, title="Select feature",
         )
         child = integration.plan_done (
            selected, actor_id=actor, skip_checks=skip_checks, strategy=strategy, resolve=resolve,
         )
         if approve:
            integration.waive_review (child)
      blockers.extend (f"{member ['alias']}: {reason}" for reason in child.get ("blockers", []))
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
      payload_schema="imp.promote-plan.v1",
      payload={
         "feature": str (group ["name"]),
         "order": [ child ["alias"] for child in children ],
         "members": children,
      },
      blockers=blockers,
   )


def _apply_one (plan: dict, actor: str, *, approve: bool) -> dict:
   """Record the approval the caller asked for, then integrate the exact candidate."""

   if approve:
      integration.approve (plan, actor)

   return integration.apply_done (plan, actor)


def _apply_group (plan: dict, actor: str, *, approve: bool) -> dict:
   """Integrate every member in order, naming what landed if one fails."""

   payload = plan ["payload"]
   completed: list [str] = []
   for child in payload ["members"]:
      try:
         with workspace.inside (child ["repository"]):
            _apply_one (child ["plan"], actor, approve=approve)
      except (state.StateError, ValueError) as error:
         landed = ", ".join (completed) or "nothing"
         raise state.StateError (f"{child ['alias']} failed after integrating {landed}: {error}") from error
      completed.append (str (child ["alias"]))

   return { "completed": completed, "feature": payload ["feature"], "order": payload ["order"] }


def _promote (
   group: dict,
   actor: str,
   *,
   yes: bool,
   dry_run: bool,
   approve: bool,
   skip_checks: bool,
   strategy: str,
   resolve: str,
   warnings: list [str],
):
   """Integrate every member of one feature in the order the caller named."""

   try:
      plan = _plan_group (
         group, actor, approve=approve, skip_checks=skip_checks, strategy=strategy, resolve=resolve,
      )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   return approval.run (
      plan,
      command="imp done",
      noun="integration",
      confirm="Integrate every member in this order?",
      plan_schema="imp.promote-plan.v1",
      result_schema="imp.promote.v2",
      apply=lambda value: _apply_group (value, actor, approve=approve),
      show=_show_group,
      success=lambda data: console.success (
         f"Feature completed across {len (data ['completed'])} repositories"
      ),
      dry_run=dry_run,
      yes=yes,
      json_output=runtime.options.json,
      warnings=warnings,
   )
