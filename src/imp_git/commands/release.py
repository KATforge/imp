from typing import Annotated

import typer

from imp_git import approval, console, git, runtime, source_release, state


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
         [
            "Push",
            f"origin: {payload ['target_ref']}, {payload ['tag']}" if payload ["push"] else "No",
         ],
         [ "Manifests", str (len (payload ["manifest_versions"])) ],
         [ "Lockfiles", str (len (payload ["lockfile_hashes"])) ],
      ],
   )
   if payload ["push"]:
      console.out.print ()
      console.label ("Commits to push")
      console.table (
         [ "Commit", "Subject" ],
         [ [ commit ["oid"] [:12], commit ["subject"] ] for commit in payload ["push_commits"] ],
      )
   console.divider ()
   console.out.print (payload ["diff"])
   console.divider ()


def release (
   patch: Annotated [bool, typer.Option ("--patch", help="Bump patch version")] = False,
   minor: Annotated [bool, typer.Option ("--minor", help="Bump minor version")] = False,
   major: Annotated [bool, typer.Option ("--major", help="Bump major version")] = False,
   set_version: Annotated [str, typer.Option ("--version", help="Use an explicit semantic version")] = "",
   local: Annotated [bool, typer.Option ("--local", help="Commit and tag without pushing or publishing")] = False,
   prerelease: Annotated [bool, typer.Option ("--prerelease", help="Publish the next release candidate")] = False,
   rc: Annotated [bool, typer.Option ("--rc", hidden=True)] = False,
):
   """Cut a source release: bump the version, commit, tag, and publish."""

   git.require ()

   dry_run = runtime.options.dry_run
   json_output = runtime.options.json
   yes = runtime.options.yes

   prerelease = prerelease or rc
   try:
      plan = source_release.plan_release (
         level=_level (patch, minor, major), prerelease=prerelease, set_version=set_version,
         local=local,
      )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      command="imp release",
      noun="shipping",
      confirm="Publish this exact source release?",
      plan_schema="imp.release-plan.v1",
      result_schema="imp.release.v1",
      apply=source_release.apply_release,
      show=_show,
      success=lambda data: console.success (f"Released {data ['tag']}"),
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
   )
