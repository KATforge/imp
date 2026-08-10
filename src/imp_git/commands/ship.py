from typing import Annotated

import typer

from imp_git import approval, console, git, plans, runtime, source_release, state

_DIRTY_AUTOMATION = """Dirty source requires a separately approved commit plan.

Next:
  imp commit --all --plan
  imp commit --apply <plan-id> --yes
  imp ship --plan

The plan ID prints with the saved plan."""


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
         [ "Release", "prerelease" if payload ["prerelease"] else "stable" ],
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
   prerelease: Annotated [bool, typer.Option ("--prerelease", help="Publish the next release candidate")] = False,
   rc: Annotated [bool, typer.Option ("--rc", hidden=True)] = False,
):
   """Create an exact source release. It never builds or deploys."""

   prerelease = prerelease or rc
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
         level=_level (patch, minor, major), prerelease=prerelease, set_version=set_version,
         source_plan_id=source_plan, persist=not dry_run,
      )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      command="imp ship",
      noun="shipping",
      confirm="Publish this exact source release?",
      plan_schema="imp.ship-plan.v2",
      result_schema="imp.release.v1",
      apply=source_release.apply_ship,
      show=_show,
      success=lambda data: console.success (f"Released {data ['tag']}"),
      plan_only=plan_only,
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
   )
