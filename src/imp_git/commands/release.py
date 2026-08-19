import re
from typing import Annotated, Any

import typer

from imp_git import approval, console, fingerprint, gh, git, plans, runtime, state, validate

_VERSION = re.compile (r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?$")


def _tag (value: str) -> str:
   version = value.removeprefix ("v")
   if not _VERSION.fullmatch (version):
      raise state.StateError ("Release version must be X.Y.Z or X.Y.Z-suffix")
   return f"v{version}"


def _notes (tag: str) -> str:
   previous = git.last_tag ()
   revision = f"{previous}..HEAD" if previous else "HEAD"
   return git.capture ("log", "--reverse", "--format=- %s", revision).strip () or f"- Release {tag}"


def _fingerprint (payload: dict [str, Any]) -> str:
   return fingerprint.values ({
      "branch": git.branch (),
      "head": git.rev_parse ("HEAD"),
      "local": payload ["local"],
      "tag": payload ["tag"],
   })


def plan_release (version: str, *, local: bool = False) -> dict [str, Any]:
   if not git.is_clean ():
      raise state.StateError ("Commit the working tree before releasing")
   tag = _tag (version)
   if git.tag_exists (tag):
      raise state.StateError (f"Release tag already exists: {tag}")
   if not local and (not git.remote_exists () or not gh.available ()):
      raise state.StateError ("Publishing requires origin and the GitHub CLI; use --local to only tag")
   branch = git.branch ()
   if not branch:
      raise state.StateError ("Release requires a checked-out branch")
   notes = _notes (tag)
   if not validate.publishable (notes):
      raise state.StateError ("Release notes contain AI attribution or an actor ID")
   payload = {
      "branch": branch,
      "head": git.rev_parse ("HEAD"),
      "local": local,
      "notes": notes,
      "prerelease": "-" in tag,
      "tag": tag,
      "version": tag.removeprefix ("v"),
   }
   return plans.build (
      "release", tag,
      scope={ "repository": git.repo_name (), "branch": payload ["branch"] },
      items=[
         { "action": "tag", "tag": tag, "oid": payload ["head"] },
         *([] if local else [
            { "action": "push", "refs": [ payload ["branch"], tag ] },
            { "action": "github_release", "tag": tag },
         ]),
      ],
      fingerprint=_fingerprint (payload),
      payload_schema="imp.release-plan.v1",
      payload=payload,
   )


def apply_release (plan: dict [str, Any]) -> dict [str, Any]:
   if plan.get ("state") != "ready" or plan.get ("payload_schema") != "imp.release-plan.v1":
      raise state.StateError ("Invalid release plan")
   payload = dict (plan ["payload"])
   if not git.is_clean () or _fingerprint (payload) != plan.get ("fingerprint"):
      raise state.StateError ("Release plan is stale")
   if git.tag_exists (str (payload ["tag"])):
      raise state.StateError (f"Release tag already exists: {payload ['tag']}")
   with state.lock ("release"):
      git.tag (str (payload ["tag"]), str (payload ["head"]))
      pushed = []
      url = ""
      if not payload ["local"]:
         git.push (ref=str (payload ["branch"]))
         git.push (ref=str (payload ["tag"]))
         pushed = [ str (payload ["branch"]), str (payload ["tag"]) ]
         url = gh.release_create (
            str (payload ["tag"]), str (payload ["notes"]), bool (payload ["prerelease"]),
         )
   plans.mark (plan, "applied", applied_at=state.now ())
   return {
      "commit_oid": payload ["head"],
      "notes": payload ["notes"],
      "pushed_refs": pushed,
      "tag": payload ["tag"],
      "url": url,
      "version": payload ["version"],
   }


def _show (plan: dict [str, Any]):
   payload = plan ["payload"]
   console.header ("Release")
   console.table ([ "Field", "Value" ], [
      [ "Tag", str (payload ["tag"]) ],
      [ "Commit", str (payload ["head"]) [:12] ],
      [ "Publish", "No" if payload ["local"] else "GitHub" ],
   ])
   console.label ("Notes")
   console.out.print (payload ["notes"])


def release (
   version: Annotated [str, typer.Argument (help="Semantic version or tag")],
   local: Annotated [bool, typer.Option ("--local", help="Tag without pushing or publishing")] = False,
):
   """Tag the current clean commit and optionally publish it."""

   git.require ()
   try:
      plan = plan_release (version, local=local)
   except state.StateError as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      command="imp release",
      noun="release",
      confirm="Create this exact release?",
      plan_schema="imp.release-plan.v1",
      result_schema="imp.release.v1",
      apply=apply_release,
      show=_show,
      success=lambda data: console.success (f"Released {data ['tag']}"),
      dry_run=runtime.options.dry_run,
      yes=runtime.options.yes,
      json_output=runtime.options.json,
   )
