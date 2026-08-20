import re
from typing import Annotated, Any

import typer

from imp_git import ai, approval, console, fingerprint, gh, git, plans, state, validate

_VERSION = re.compile (r"^v?(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$")


def _tag (value: str) -> str:
   match = _VERSION.fullmatch (value)
   if not match:
      raise state.StateError ("Release version must be X.Y.Z or X.Y.Z-rc.N")
   version = ".".join (match.groups () [:3])
   if match.group (4):
      version += f"-rc.{match.group (4)}"
   return f"v{version}"


def _known () -> list [tuple [tuple [int, int, int], int | None]]:
   names = set (git.tags ())
   if git.remote_exists ():
      names.update (git.remote_tags ())
   values = []
   for name in names:
      match = _VERSION.fullmatch (name)
      if match:
         values.append ((tuple (map (int, match.groups () [:3])), int (match.group (4)) if match.group (4) else None))
   return values


def _next (mode: str) -> str:
   known = _known ()
   stable = { version for version, rc in known if rc is None }
   current = max (stable, default=(0, 0, 0))
   pending = [
      (version, rc) for version, rc in known
      if rc is not None and version not in stable and version > current
   ]
   if mode == "stable":
      if not pending:
         raise state.StateError ("No release candidate to stabilize")
      return ".".join (map (str, max (version for version, _rc in pending)))
   if mode == "rc":
      if pending:
         version = max (version for version, _rc in pending)
         number = max (rc for candidate, rc in pending if candidate == version) + 1
      else:
         version = current [0], current [1], current [2] + 1
         number = 1
      return f"{'.'.join (map (str, version))}-rc.{number}"
   index = { "major": 0, "minor": 1, "patch": 2 } [mode]
   version = list (current)
   version [index] += 1
   for position in range (index + 1, 3):
      version [position] = 0
   return ".".join (map (str, version))


def _notes (tag: str) -> str:
   """Condense the commit subjects since the last tag into a few essential bullets.

   AI keeps only what a user would care about; an unreachable provider falls back
   to the raw subject list, so a release never blocks on the AI.
   """

   previous = git.last_tag ()
   revision = f"{previous}..HEAD" if previous else "HEAD"
   subjects = git.capture ("log", "--reverse", "--format=- %s", revision).strip ()
   if len (subjects.splitlines ()) < 2:
      return subjects or f"- Release {tag}"
   try:
      condensed = ai.release_notes (subjects, tag)
   except (state.StateError, typer.Exit):
      return subjects
   if condensed and validate.publishable (condensed):
      return condensed
   return subjects


def _fingerprint (payload: dict [str, Any]) -> str:
   return fingerprint.values ({
      "branch": git.branch (),
      "head": git.rev_parse ("HEAD"),
      "local": payload ["local"],
      "tag": payload ["tag"],
   })


def plan_release (version: str = "", *, bump: str = "", local: bool = False) -> dict [str, Any]:
   if not git.is_clean ():
      raise state.StateError ("Commit the working tree before releasing")
   if version and bump:
      raise state.StateError ("Use a version or one SemVer flag")
   tag = _tag (version or _next (bump or "patch"))
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
   version: Annotated [str, typer.Argument (help="Explicit semantic version or tag")] = "",
   local: Annotated [bool, typer.Option ("--local", help="Tag without pushing or publishing")] = False,
   major: Annotated [bool, typer.Option ("--major", help="Increment the major version")] = False,
   minor: Annotated [bool, typer.Option ("--minor", help="Increment the minor version")] = False,
   patch: Annotated [bool, typer.Option ("--patch", help="Increment the patch version")] = False,
   rc: Annotated [bool, typer.Option ("--rc", help="Create or increment a release candidate")] = False,
   stable: Annotated [bool, typer.Option ("--stable", help="Promote the latest release candidate")] = False,
):
   """Tag the current clean commit as a SemVer release and publish it to GitHub.

   With no version it increments patch; pass an exact version or one SemVer flag.
   Release notes are AI-condensed from the commit subjects since the previous tag:
   at most six one-line bullets covering only what users care about, shown for
   approval before anything is tagged; an unreachable AI falls back to the raw
   subject list. Pushes the branch and tag then creates the GitHub release; --local
   only tags. Refuses notes containing AI attribution or actor IDs. Always confirms,
   since it writes to a remote.
   """

   git.require ()
   try:
      modes = [ name for name, enabled in (
         ("major", major), ("minor", minor), ("patch", patch), ("rc", rc), ("stable", stable),
      ) if enabled ]
      if len (modes) > 1:
         raise state.StateError ("Use one SemVer flag")
      plan = plan_release (version, bump=modes [0] if modes else "", local=local)
   except state.StateError as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      noun="release",
      confirm="Create this exact release?",
      result_schema="imp.release.v1",
      apply=apply_release,
      show=_show,
      success=lambda data: console.success (f"Released {data ['tag']}"),
      destructive=not local,
   )
