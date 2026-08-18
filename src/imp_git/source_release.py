import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from imp_git import fingerprint, gh, git, identity, plans, state, summary, validate, version

_LOCK_COMMANDS = {
   "bun.lock": [ "bun", "install", "--lockfile-only", "--ignore-scripts" ],
   "bun.lockb": [ "bun", "install", "--lockfile-only", "--ignore-scripts" ],
   "composer.lock": [ "composer", "update", "--lock", "--no-install", "--no-scripts" ],
   "package-lock.json": [ "npm", "install", "--package-lock-only", "--ignore-scripts" ],
   "pnpm-lock.yaml": [ "pnpm", "install", "--lockfile-only", "--ignore-scripts" ],
   "uv.lock": [ "uv", "lock" ],
   "yarn.lock": [ "yarn", "install", "--mode=update-lockfile", "--ignore-scripts" ],
}

_FALLBACK = "- Changed the source release"

_DIRTY_SOURCE = """Uncommitted changes cannot be shipped.

Next:
  imp --dry-run commit --all
  imp --yes commit --all
  imp release"""


def _hash (path: Path) -> str:
   return f"sha256:{hashlib.sha256 (path.read_bytes ()).hexdigest ()}"


def _repository_url (tag: str) -> str:
   remote = git.remote_url ().removesuffix (".git")
   if remote.startswith ("git@github.com:"):
      remote = f"https://github.com/{remote.removeprefix ('git@github.com:')}"
   return f"{remote}/releases/tag/{tag}"


def _temporary_worktree (ref: str) -> tuple [Path, Any]:
   root = Path (tempfile.mkdtemp (prefix="imp-release-"))
   path = root / "worktree"
   git.worktree_add_detached (str (path), ref)

   def cleanup ():
      if path.exists ():
         git.worktree_remove (str (path), force=True)
      shutil.rmtree (root, ignore_errors=True)

   return path, cleanup


def _release_tags () -> list [str]:
   """Every release tag this repository knows of, local and published.

   Names are all that version discovery needs, and the remote already answers for
   them, so a local tag that disagrees with origin can never decide a release.
   """

   names = set (git.tags ())
   if git.remote_exists ():
      names.update (git.remote_tags ())

   return sorted (names)


def _latest_version (names: list [str]) -> str:
   highest = version.highest (names)
   return highest.lstrip ("v") if highest else "0.0.0"


def _range_tag (names: list [str]) -> tuple [str, list [str]]:
   """Return the tag bounding the changelog, fetching only that one when it is missing.

   This is the sole place a release needs a tag as an object rather than a name, so
   it is the only tag fetched. Nothing else in the repository is touched or moved.
   """

   tag = version.highest (names)
   if not tag or git.tag_exists (tag):
      return tag, []
   if git.remote_exists () and git.fetch_tag (tag):
      return tag, []

   return "", [ f"Could not read {tag} locally, so the changelog covers every commit" ]


def _entry (source_oid: str, names: list [str]) -> tuple [str, str, list [str]]:
   tag, warnings = _range_tag (names)
   range_value = f"{tag}..{source_oid}" if tag else source_oid

   return tag, version.changelog_from_commits (_described (range_value)) or _FALLBACK, warnings


def _described (range_value: str) -> str:
   """Every described change in a range, reading a squash body as the work it carries.

   Integrating with `squash` keeps one commit whose subject names the feature and whose
   body lists what landed. The body is the record; the subject alone says nothing.
   """

   lines: list [str] = []
   raw = git.capture ("log", "--no-merges", "--format=%s%x1f%b%x1e", range_value)
   for record in raw.split ("\x1e"):
      subject, _, body = record.strip ().partition ("\x1f")
      carried = [
         value.strip () [2:] for value in body.splitlines () if value.strip ().startswith ("- ")
      ] if subject.strip ().startswith (summary.INTEGRATE) else []
      lines.extend (carried or ([ subject.strip () ] if subject.strip () else []))

   return "\n".join (lines)


def _refresh_lockfiles (root: Path, manifests: list [Path]) -> tuple [list [dict [str, Any]], dict [str, str]]:
   if not manifests:
      return [], {}
   commands = []
   hashes = {}
   for name, argv in _LOCK_COMMANDS.items ():
      path = root / name
      if not path.is_file ():
         continue
      if not shutil.which (argv [0]):
         raise state.StateError (f"Cannot refresh {name}: {argv [0]} is not installed")
      before = _hash (path)
      process = subprocess.run (argv, cwd=root, capture_output=True, text=True, timeout=900, check=False)
      if process.returncode:
         detail = (process.stderr or process.stdout).strip () [-2000:]
         raise state.StateError (f"Cannot refresh {name}: {detail}")
      after = _hash (path)
      commands.append ({ "lockfile": name, "run": argv })
      hashes [name] = after
      if before == after:
         continue
   return commands, hashes


def _source () -> tuple [str, str, str]:
   target = git.base_branch ()
   if not git.ref_exists (target):
      raise state.StateError (f"No trunk branch to release from: {target}")
   if git.remote_exists ():
      git.fetch (
         no_tags=True, remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}",
      )
   source_oid = git.rev_parse (target)
   public = git.rev_parse (f"origin/{target}") if git.remote_exists () else ""

   return source_oid, target, public


def _published (tag: str) -> bool:
   """Return whether one tag has finished reaching everywhere it belongs."""

   if not git.remote_exists ():
      return True
   if tag not in git.remote_tags ():
      return False

   return not gh.available () or bool (gh.release_view (tag))


def _resumable (tag: str, source_oid: str) -> str:
   """Return the release commit an unfinished run already made for this tag.

   A release builds its commit, tags it, moves the target, pushes, and publishes, in
   that order. Every step after the tag can fail on its own, leaving the tag as the
   only evidence. Two shapes mean unfinished work rather than a completed release:
   a tag one commit ahead of the target, whose target never moved, and a tag on the
   target that never reached the remote or never became a release.
   """

   if not git.tag_exists (tag):
      return ""
   tagged = git.rev_parse (tag)
   parents = git.capture ("rev-list", "--parents", "-n", "1", tagged).split () [1:]
   if parents == [ source_oid ]:
      return tagged

   return tagged if tagged == source_oid and not _published (tag) else ""


def plan_release (
   *,
   level: str = "patch",
   prerelease: bool = False,
   set_version: str = "",
   local: bool = False,
   persist: bool = True,
) -> dict [str, Any]:
   if level not in { "patch", "minor", "major" }:
      raise state.StateError (f"Unsupported version level: {level}")
   if not git.is_clean ():
      raise state.StateError (_DIRTY_SOURCE)
   source_oid, target_ref, public_target_oid = _source ()
   names = _release_tags ()
   current = _latest_version (names)
   resumed = "" if set_version else _resumable (f"v{current}", source_oid)
   if resumed:
      new_version = current
   else:
      base_version = set_version or version.bump (current, level)
      if version.base_tuple (base_version) is None or "-" in base_version:
         raise state.StateError (f"Release version must be X.Y.Z: {base_version}")
      existing = [ name for name in names if name.startswith (f"v{base_version}-rc.") ]
      new_version = version.next_rc (base_version, existing) if prerelease else base_version
   tag = f"v{new_version}"
   if not resumed and tag in names:
      raise state.StateError (f"Release tag already exists: {tag}")
   previous_tag, entry, notes = _entry (source_oid, names)
   worktree, cleanup = _temporary_worktree (source_oid)
   try:
      changed = version.sync_manifests (worktree, new_version)
      manifest_versions = {
         str (path.relative_to (worktree)): new_version for path in changed
      }
      lock_commands, lock_hashes = _refresh_lockfiles (worktree, changed)
      git.run_at (str (worktree), "add", "-A")
      tree_oid = git.run_at (str (worktree), "write-tree").stdout.strip ()
      commit_oid = resumed or git.commit_tree_parents (tree_oid, [ source_oid ], f"chore: release {tag}")
      diff = git.capture ("diff", "--binary", source_oid, commit_oid)
   finally:
      cleanup ()
   payload = {
      "changelog": entry,
      "commit_oid": commit_oid,
      "commit_tree_oid": git.tree (commit_oid),
      "diff": diff,
      "github_release": not local and gh.available () and git.remote_exists (),
      "resumed": bool (resumed),
      "level": level,
      "lock_commands": lock_commands,
      "lockfile_hashes": lock_hashes,
      "manifest_versions": manifest_versions,
      "previous_tag": previous_tag,
      "prerelease": prerelease,
      "public_target_oid": public_target_oid,
      "push": not local and git.remote_exists (),
      "repository": git.repo_name (),
      "source_oid": source_oid,
      "local": local,
      "tag": tag,
      "target_ref": target_ref,
      "version": new_version,
   }
   plan_fingerprint = fingerprint.values ({
      "source_oid": source_oid,
      "tag": tag,
      "target_ref": target_ref,
      "version": new_version,
      "prerelease": prerelease,
      "local": local,
   })
   return plans.build (
      "release", new_version,
      scope={ "repository": git.repo_name (), "target": target_ref },
      items=[
         { "action": "update_ref", "ref": target_ref, "oid": commit_oid },
         { "action": "tag", "tag": tag, "oid": commit_oid },
         *([ { "action": "push", "refs": [ target_ref, tag ] } ] if payload ["push"] else []),
         *([ { "action": "github_release", "tag": tag } ] if payload ["github_release"] else []),
      ],
      fingerprint=plan_fingerprint,
      warnings=notes,
      payload_schema="imp.release-plan.v1",
      payload=payload,
   )


def _validate (plan: dict [str, Any]) -> dict [str, Any]:
   if plan.get ("payload_schema") != "imp.release-plan.v1":
      raise state.StateError ("Unsupported source-release plan")
   if plan.get ("state") != "ready":
      raise state.StateError (f"Source-release plan is {plan.get ('state')}")
   payload = dict (plan ["payload"])
   if not git.ref_exists (payload ["commit_oid"]):
      raise state.StateError ("Planned source-release candidate is missing")
   target_oid = git.rev_parse (payload ["target_ref"])
   if target_oid not in { payload ["source_oid"], payload ["commit_oid"] }:
      raise state.StateError ("Release target does not match the tested source candidate")
   if git.tag_exists (payload ["tag"]) and git.rev_parse (payload ["tag"]) != payload ["commit_oid"]:
      raise state.StateError (f"Release tag points to another commit: {payload ['tag']}")
   if target_oid == payload ["source_oid"] and payload ["tag"] in git.remote_tags ():
      raise state.StateError (f"Release tag already exists remotely: {payload ['tag']}")
   if not validate.publishable (str (payload ["changelog"])):
      raise state.StateError ("Release notes contain AI attribution or an actor ID")
   return payload


def _recovery (plan: dict [str, Any], completed: list [str], error: Exception):
   recovery_id = identity.resource ("recovery", "release", str (plan ["label"]), str (len (completed) + 1))
   state.atomic_write (
      state.root () / "recovery" / f"{identity.key (recovery_id)}.json",
      {
         "schema": "imp.recovery.v1",
         "command": "imp release",
         "completed": completed,
         "created_at": state.now (),
         "error": str (error),
         "next": "imp release",
         "recovery_id": recovery_id,
      },
   )


def apply_release (plan: dict [str, Any]) -> dict [str, Any]:
   completed = []
   try:
      with state.lock ("release"):
         payload = _validate (plan)
         target_ref = str (payload ["target_ref"])
         for path in git.ref_worktrees (target_ref):
            if not git.clean_at (path):
               raise state.StateError (f"Release target worktree is dirty: {path}")
         if git.rev_parse (target_ref) == payload ["source_oid"]:
            git.update_ref_checked (
               f"refs/heads/{target_ref}", payload ["commit_oid"], payload ["source_oid"]
            )
            for path in git.ref_worktrees (target_ref):
               git.reset_at (path, payload ["commit_oid"])
         completed.append ("commit")
         if not git.tag_exists (payload ["tag"]):
            git.tag (payload ["tag"], payload ["commit_oid"])
         completed.append ("tag")
         pushed_refs = []
         if payload ["push"]:
            git.push (ref=target_ref)
            pushed_refs.append (f"refs/heads/{target_ref}")
            git.push (ref=payload ["tag"])
            pushed_refs.append (f"refs/tags/{payload ['tag']}")
            completed.append ("push")
         release_url = ""
         if payload ["github_release"]:
            existing = gh.release_view (payload ["tag"])
            if existing and bool (existing.get ("isPrerelease")) != bool (payload ["prerelease"]):
               raise state.StateError (f"GitHub release type does not match the plan for {payload ['tag']}")
            if not existing:
               created = gh.release_create (
                  payload ["version"],
                  payload ["changelog"],
                  prerelease=bool (payload ["prerelease"]),
               )
               if not created:
                  raise state.StateError (f"GitHub release creation failed for {payload ['tag']}")
            release_url = str (existing.get ("url") or _repository_url (payload ["tag"]))
            completed.append ("github_release")
         receipt = {
            "source_release_id": identity.resource ("source-release", git.repo_name (), payload ["tag"]),
            "repository": git.repo_name (),
            "version": payload ["version"],
            "tag": payload ["tag"],
            "commit_oid": payload ["commit_oid"],
            "changelog": payload ["changelog"],
            "pushed_refs": pushed_refs,
            "release_url": release_url,
            "manifest_versions": payload ["manifest_versions"],
            "updated_lockfiles": sorted (payload ["lockfile_hashes"]),
            "prerelease": bool (payload ["prerelease"]),
         }
         state.atomic_write (
            state.root () / "releases" / f"{identity.key (receipt ['source_release_id'])}.json",
            { "schema": "imp.source-release.v2", **receipt, "created_at": state.now () },
         )
         plans.mark (plan, "applied", applied_at=state.now ())
         state.clear_recovery (str (plan ["label"]))
         return receipt
   except Exception as error:
      _recovery (plan, completed, error)
      raise
