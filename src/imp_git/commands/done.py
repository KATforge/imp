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
   result,
   roster,
   runtime,
   spans,
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
   if inside and not keep:
      _warn_if_standing_here ()

   actor_id = runtime.options.actor_id
   dry_run = runtime.options.dry_run
   json_output = runtime.options.json
   yes = runtime.options.yes

   actor = identity.actor (actor_id)

   if resolve and resolve not in { "ours", "theirs", "edit", "ai", "ask" }:
      console.fatal (f"Unsupported conflict resolution: {resolve}")
   resolution = "resolve" if resolve == "ai" else resolve

   if all_ready:
      return _promote_every (
         actor, yes=yes, dry_run=dry_run, skip_checks=skip_checks,
         strategy=strategy, resolve=resolution,
      )

   group = _group (feature)
   if not group and not inside:
      git.require ()
   if group:
      return _promote (
         group, actor, yes=yes, dry_run=dry_run,
         skip_checks=skip_checks, strategy=strategy, resolve=resolution,
      )

   if approve and dry_run:
      console.fatal ("--approve cannot be combined with --dry-run")
   try:
      selected = _feature (feature)
      plan = integration.plan_done (
         selected, actor_id=actor, into=into, keep=keep,
         skip_checks=skip_checks, strategy=strategy, resolve=resolution,
      )
      if approve:
         integration.approve (plan, actor)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   return approval.run (
      plan,
      command="imp done",
      noun="completion",
      confirm="Apply this exact integration plan?",
      plan_schema="imp.done-plan.v1",
      result_schema="imp.done.v1",
      apply=lambda value: integration.apply_done (value, actor),
      show=_show,
      success=lambda data: console.success ("Feature completed"),
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
   )


def _warn_if_standing_here ():
   """Warn when the caller stands in a worktree this run will remove.

   Integration deletes the feature worktree, which leaves the calling shell in a
   directory that no longer exists. Imp itself steps out, but the shell cannot, so
   the next prompt reports a missing working directory as though something failed.
   """

   try:
      here = Path.cwd ().resolve ()
   except OSError:
      return
   for feature in features.all ():
      if feature.get ("state") not in { "active", "awaiting-merge" }:
         continue
      path = Path (str (feature ["path"])).resolve ()
      if here == path or path in here.parents:
         console.warn (f"You are standing in {path}, which this removes; run from the repository root")
         return


def _promote_every (
   actor: str,
   *,
   yes: bool,
   dry_run: bool,
   skip_checks: bool,
   strategy: str,
   resolve: str,
):
   """Integrate every ready feature in turn, approved once.

   Each feature still builds its own candidate against the trunk of the moment and
   lands before the next one starts, so this automates the loop rather than stacking
   unvalidated work into a single merge. The run stops at the first failure and says
   what landed, because continuing past one would bury it.
   """

   value = workspace.here ()
   if not value:
      console.fatal ("Not a git repository, and no repositories below this directory")

   entries = roster.collect (value)
   ready = roster.promotable (entries)
   skipped = [ entry for entry in entries if entry not in ready ]
   if not ready:
      console.fatal (f"Nothing is ready to integrate in {value ['name']}")

   console.header (f"Integrate {len (ready)} feature(s) · {value ['name']}")
   console.table (
      [ "Feature", "Repositories", "Age" ],
      [ [ str (e ["name"]), " ".join (e ["repositories"]), str (e ["age"]) ] for e in ready ],
   )
   for entry in skipped:
      console.muted (f"  skipping {entry ['name']} ({entry ['condition']})")

   data = {
      "landed": [],
      "ready": [ str (entry ["name"]) for entry in ready ],
      "skipped": [ str (entry ["name"]) for entry in skipped ],
      "workspace": value ["name"],
   }
   if dry_run:
      result.emit ("imp.promote-all.v1", "imp done", data, json_output=runtime.options.json)
      return data
   if not yes and not console.confirm (f"Integrate all {len (ready)} in this order?"):
      raise typer.Exit (0)

   for entry in ready:
      group = {
         "name": str (entry ["name"]),
         "members": roster.ordered_members (value, entry),
         "workspace": value,
      }
      try:
         _promote (
            group, actor, yes=True, dry_run=False,
            skip_checks=skip_checks, strategy=strategy, resolve=resolve,
         )
      except (state.StateError, ValueError, typer.Exit) as error:
         console.err (f"Stopped at {entry ['name']}: {error}")
         break
      data ["landed"].append (str (entry ["name"]))

   if runtime.options.json:
      result.emit ("imp.promote-all.v1", "imp done", data, json_output=True)
      return data
   console.success (f"Integrated {len (data ['landed'])} of {len (ready)}")

   return data


def _group (feature: str) -> dict | None:
   """Resolve one feature to its members across the workspace, or None for a plain feature."""

   value = workspace.here ()
   if not value:
      return None
   inside = git.succeeds ("rev-parse", "--git-dir")

   if not feature:
      return None if inside else _pick (value)

   span = spans.find (value, feature)
   if span:
      members = spans.members (value, span)
      return { "name": str (span ["name"]), "members": members, "workspace": value }

   entry = next ((row for row in roster.collect (value) if row ["name"] == feature), None)
   if not entry or (inside and len (entry ["members"]) < 2):
      return None

   return {
      "name": str (entry ["name"]),
      "members": roster.ordered_members (value, entry),
      "workspace": value,
   }


def _pick (value: dict) -> dict:
   entries = roster.collect (value)
   ready = roster.promotable (entries)
   if not ready:
      console.fatal (f"Nothing is ready to promote in {value ['name']}")
   labels = {
      f"{entry ['name']}   {' '.join (entry ['repositories'])}   {entry ['age']}": entry
      for entry in ready
   }
   console.header (f"Promote to trunk · {value ['name']}")
   entry = labels [console.choose ("Select a feature", list (labels))]

   return {
      "name": str (entry ["name"]),
      "members": roster.ordered_members (value, entry),
      "workspace": value,
   }


def _plan_group (group: dict, actor: str, *, skip_checks: bool, strategy: str, resolve: str) -> list [dict]:
   children = []
   for member in group ["members"]:
      with spans.inside (member ["repository"]):
         selected = features.resolve (
            str (group ["name"]), states={ "active", "awaiting-merge" }, title="Select feature",
         )
         plan = integration.plan_done (
            selected, actor_id=actor, skip_checks=skip_checks, strategy=strategy, resolve=resolve,
         )
      children.append ({ "alias": member ["alias"], "repository": member ["repository"], "plan": plan })

   return children


def _promote (
   group: dict,
   actor: str,
   *,
   yes: bool,
   dry_run: bool,
   skip_checks: bool,
   strategy: str,
   resolve: str,
):
   """Integrate every member of one feature in dependency-first order."""

   try:
      children = _plan_group (group, actor, skip_checks=skip_checks, strategy=strategy, resolve=resolve)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   blockers = [
      f"{child ['alias']}: {value}"
      for child in children
      for value in child ["plan"].get ("blockers", [])
   ]
   console.header (f"Complete feature: {group ['name']}")
   console.table (
      [ "Repository", "Strategy", "Candidate" ],
      [
         [
            str (child ["alias"]),
            str (child ["plan"] ["payload"] ["strategy"]),
            str (child ["plan"] ["payload"] ["candidate_oid"]) [:12],
         ]
         for child in children
      ],
   )
   for blocker in blockers:
      console.err (blocker)

   data = {
      "blocked": bool (blockers),
      "blockers": blockers,
      "feature": group ["name"],
      "order": [ child ["alias"] for child in children ],
   }
   if blockers:
      if runtime.options.json:
         return result.emit ("imp.promote.v1", "imp done", data, json_output=True)
      console.fatal ("Every member must be ready before a spanning feature integrates")

   if dry_run:
      return result.emit ("imp.promote.v1", "imp done", data, json_output=runtime.options.json)

   if not yes and not console.confirm ("Integrate every member in this order?"):
      raise typer.Exit (0)

   completed = []
   try:
      for child in children:
         with spans.inside (child ["repository"]):
            integration.apply_done (child ["plan"], actor)
         completed.append (child ["alias"])
   except (state.StateError, ValueError) as error:
      console.err (f"Integrated before failing: {', '.join (completed) or 'nothing'}")
      console.fatal (str (error))

   value = group ["workspace"]
   span = spans.find (value, str (group ["name"]))
   if span:
      spans.forget (value, span)
   data ["completed"] = completed
   if runtime.options.json:
      return result.emit ("imp.promote.v1", "imp done", data, json_output=True)
   console.success (f"Feature completed across {len (completed)} repositories")

   return data
