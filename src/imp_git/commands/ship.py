from typing import Annotated

import typer

from imp_git import console, git, plans, result, runtime, source_release, state

_DIRTY_AUTOMATION = """Dirty source requires a separately approved commit plan.

Next:
  imp commit --all --plan
  imp commit --apply <plan-id> --yes
  imp ship --plan"""


def _level (patch: bool, minor: bool, major: bool) -> str:
   if sum ([ patch, minor, major ]) > 1:
      raise state.StateError ("--patch, --minor, and --major are mutually exclusive")
   if major:
      return "major"
   if minor:
      return "minor"
   return "patch"


def _show (plan: dict):
   payload = plan ["payload"]
   console.header ("Source release")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Version", str (payload ["version"]) ],
         [ "Tag", str (payload ["tag"]) ],
         [ "Target", str (payload ["target_ref"]) ],
         [ "Candidate", str (payload ["commit_oid"]) [:12] ],
         [ "Manifests", str (len (payload ["manifest_versions"])) ],
         [ "Lockfiles", str (len (payload ["lockfile_hashes"])) ],
      ],
   )
   console.divider ()
   console.out.print (payload ["diff"])
   console.divider ()


def ship (
   patch: Annotated [bool, typer.Option ("--patch", help="Bump patch version")] = False,
   minor: Annotated [bool, typer.Option ("--minor", help="Bump minor version")] = False,
   major: Annotated [bool, typer.Option ("--major", help="Bump major version")] = False,
   set_version: Annotated [str, typer.Option ("--version", help="Use an explicit semantic version")] = "",
   source_plan: Annotated [str, typer.Option ("--source-plan", help="Build from an exact imp done candidate")] = "",
   plan_only: Annotated [bool, typer.Option ("--plan", help="Prepare the exact release candidate only")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply one saved source-release plan")] = "",
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the displayed plan")] = False,
   dry_run: Annotated [bool, typer.Option ("--dry-run", help="Display an ephemeral plan")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
   include_dirty: Annotated [
      bool,
      typer.Option ("--include-dirty", help="Commit dirty work with separate approval"),
   ] = False,
   rc: Annotated [bool, typer.Option ("--rc", hidden=True)] = False,
   stable: Annotated [bool, typer.Option ("--stable", hidden=True)] = False,
   squash: Annotated [bool, typer.Option ("--squash", hidden=True)] = False,
):
   """Create an exact source release. It never builds or deploys."""

   del rc, stable, squash
   if include_dirty and not git.is_clean ():
      machine = json_output or runtime.options.json or runtime.options.no_input
      if machine or yes or runtime.options.yes:
         console.fatal (_DIRTY_AUTOMATION)
      from imp_git.commands.commit import commit

      commit (all=True)
   yes = yes or runtime.options.yes
   dry_run = dry_run or runtime.options.dry_run
   try:
      plan = plans.resolve ("ship", "" if apply == "__pick__" else apply) if apply else source_release.plan_ship (
         level=_level (patch, minor, major), set_version=set_version,
         source_plan_id=source_plan, persist=not dry_run,
      )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   machine = json_output or runtime.options.json
   if not machine:
      _show (plan)
   if plan_only or dry_run:
      if machine:
         result.emit ("imp.ship-plan.v1", "imp ship", { "plan": plan }, json_output=True)
      return plan
   if runtime.options.no_input and not yes:
      console.fatal ("Non-interactive shipping requires --plan or --apply <plan-id> --yes")
   if not yes and not console.confirm ("Publish this exact source release?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)
   try:
      data = source_release.apply_ship (plan)
   except state.StateError as error:
      console.fatal (str (error))
   if machine:
      result.emit ("imp.release.v1", "imp ship", data, json_output=True)
   else:
      console.success (f"Released {data ['tag']}")
   return data
