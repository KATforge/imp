import hashlib
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from imp_git import fingerprint, gh, git, identity, plans, state, validate, version

_LOCK_COMMANDS = {
   "bun.lock": [ "bun", "install", "--lockfile-only", "--ignore-scripts" ],
   "bun.lockb": [ "bun", "install", "--lockfile-only", "--ignore-scripts" ],
   "composer.lock": [ "composer", "update", "--lock", "--no-install", "--no-scripts" ],
   "package-lock.json": [ "npm", "install", "--package-lock-only", "--ignore-scripts" ],
   "pnpm-lock.yaml": [ "pnpm", "install", "--lockfile-only", "--ignore-scripts" ],
   "uv.lock": [ "uv", "lock" ],
   "yarn.lock": [ "yarn", "install", "--mode=update-lockfile", "--ignore-scripts" ],
}


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


def _latest_version () -> str:
   highest = git.highest_tag (stable=True)
   return highest.lstrip ("v") if highest else "0.0.0"


def _entry (source_oid: str) -> tuple [str, str]:
   tag = git.highest_tag (stable=True)
   range_value = f"{tag}..{source_oid}" if tag else source_oid
   subjects = git.capture ("log", "--format=%h %s", range_value)
   return tag, version.changelog_from_commits (subjects) or "- Changed the source release"


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


def _source (
   source_plan_id: str,
) -> tuple [str, str, str, dict [str, Any] | None]:
   if not source_plan_id:
      branch = git.branch ()
      if not branch:
         raise state.StateError ("imp ship requires a branch or --source-plan")
      return git.rev_parse (branch), branch, git.rev_parse (branch), None
   source_plan = plans.load (source_plan_id)
   if source_plan.get ("payload_schema") != "imp.done-plan.v1":
      raise state.StateError ("--source-plan must name an imp done plan")
   payload = source_plan ["payload"]
   if source_plan.get ("state") != "ready":
      raise state.StateError ("Source integration plan is not ready")
   return payload ["candidate_oid"], payload ["target_ref"], payload ["local_target_oid"], source_plan


def plan_ship (
   *,
   level: str = "patch",
   set_version: str = "",
   source_plan_id: str = "",
   persist: bool = True,
) -> dict [str, Any]:
   if level not in { "patch", "minor", "major" }:
      raise state.StateError (f"Unsupported version level: {level}")
   if not source_plan_id and not git.is_clean ():
      raise state.StateError ("imp ship requires clean approved source")
   if git.remote_exists ():
      git.fetch (tags=True)
   source_oid, target_ref, public_target_oid, source_plan = _source (source_plan_id)
   current = _latest_version ()
   new_version = set_version or version.bump (current, level)
   tag = f"v{new_version}"
   if git.tag_exists (tag) or tag in git.remote_tags ():
      raise state.StateError (f"Release tag already exists: {tag}")
   previous_tag, entry = _entry (source_oid)
   worktree, cleanup = _temporary_worktree (source_oid)
   try:
      changed = version.sync_manifests (worktree, new_version)
      manifest_versions = {
         str (path.relative_to (worktree)): new_version for path in changed
      }
      changelog = worktree / "CHANGELOG.md"
      changelog.write_text (
         version.consume_unreleased (changelog, new_version, date.today ().isoformat (), entry)
      )
      lock_commands, lock_hashes = _refresh_lockfiles (worktree, changed)
      git.run_at (str (worktree), "add", "-A")
      tree_oid = git.run_at (str (worktree), "write-tree").stdout.strip ()
      commit_oid = git.commit_tree_parents (tree_oid, [ source_oid ], f"chore: release {tag}")
      diff = git.capture ("diff", "--binary", source_oid, commit_oid)
   finally:
      cleanup ()
   payload = {
      "changelog": entry,
      "commit_oid": commit_oid,
      "commit_tree_oid": git.tree (commit_oid),
      "depends_on": [source_plan_id] if source_plan_id else [],
      "diff": diff,
      "github_release": gh.available () and git.remote_exists (),
      "level": level,
      "lock_commands": lock_commands,
      "lockfile_hashes": lock_hashes,
      "manifest_versions": manifest_versions,
      "previous_tag": previous_tag,
      "public_target_oid": public_target_oid,
      "push": git.remote_exists (),
      "repository": git.repo_name (),
      "source_oid": source_oid,
      "source_plan_fingerprint": source_plan.get ("fingerprint") if source_plan else "",
      "source_plan_id": source_plan_id,
      "tag": tag,
      "target_ref": target_ref,
      "version": new_version,
   }
   plan_fingerprint = fingerprint.values ({
      "source_oid": source_oid,
      "source_plan_fingerprint": payload ["source_plan_fingerprint"],
      "tag": tag,
      "target_ref": target_ref,
      "version": new_version,
   })
   return plans.create (
      "ship", new_version,
      scope={ "repository": git.repo_name (), "target": target_ref },
      items=[
         { "action": "update_ref", "ref": target_ref, "oid": commit_oid },
         { "action": "tag", "tag": tag, "oid": commit_oid },
         *([ { "action": "push", "refs": [ target_ref, tag ] } ] if payload ["push"] else []),
         *([ { "action": "github_release", "tag": tag } ] if payload ["github_release"] else []),
      ],
      fingerprint=plan_fingerprint,
      payload_schema="imp.ship-plan.v1",
      payload=payload,
      persist=persist,
   )


def _validate (plan: dict [str, Any]) -> dict [str, Any]:
   if plan.get ("payload_schema") != "imp.ship-plan.v1":
      raise state.StateError ("Unsupported source-release plan")
   if plan.get ("state") != "ready":
      raise state.StateError (f"Source-release plan is {plan.get ('state')}")
   payload = dict (plan ["payload"])
   if not git.ref_exists (payload ["commit_oid"]):
      raise state.StateError ("Planned source-release candidate is missing")
   if git.rev_parse (payload ["target_ref"]) != payload ["source_oid"]:
      raise state.StateError ("Release target does not match the tested source candidate")
   if git.tag_exists (payload ["tag"]) or payload ["tag"] in git.remote_tags ():
      raise state.StateError (f"Release tag already exists: {payload ['tag']}")
   if payload ["source_plan_id"]:
      source_plan = plans.load (payload ["source_plan_id"])
      if source_plan.get ("fingerprint") != payload ["source_plan_fingerprint"]:
         raise state.StateError ("Source integration plan changed")
   if not validate.publishable (str (payload ["changelog"])):
      raise state.StateError ("Release notes contain AI attribution or an actor ID")
   return payload


def _recovery (plan: dict [str, Any], completed: list [str], error: Exception):
   recovery_id = identity.resource ("recovery", "ship", str (plan ["label"]), str (len (completed) + 1))
   state.atomic_write (
      state.root () / "recovery" / f"{identity.key (recovery_id)}.json",
      {
         "schema": "imp.recovery.v1",
         "command": "imp ship",
         "completed": completed,
         "created_at": state.now (),
         "error": str (error),
         "next": f"imp ship --apply {plan ['plan_id']} --yes",
         "plan_id": plan ["plan_id"],
         "recovery_id": recovery_id,
      },
   )


def apply_ship (plan: dict [str, Any]) -> dict [str, Any]:
   completed = []
   try:
      with state.lock ("release"):
         payload = _validate (plan)
         target_ref = str (payload ["target_ref"])
         for path in git.ref_worktrees (target_ref):
            if not git.clean_at (path):
               raise state.StateError (f"Release target worktree is dirty: {path}")
         git.update_ref_checked (
            f"refs/heads/{target_ref}", payload ["commit_oid"], payload ["source_oid"]
         )
         for path in git.ref_worktrees (target_ref):
            git.reset_at (path, payload ["commit_oid"])
         completed.append ("commit")
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
         if payload ["github_release"] and gh.release_create (payload ["version"], payload ["changelog"]):
            release_url = _repository_url (payload ["tag"])
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
            "plan_id": plan ["plan_id"],
         }
         state.atomic_write (
            state.root () / "releases" / f"{identity.key (receipt ['source_release_id'])}.json",
            { "schema": "imp.source-release.v1", **receipt, "created_at": state.now () },
         )
         plans.mark (plan, "applied", applied_at=state.now ())
         return receipt
   except Exception as error:
      _recovery (plan, completed, error)
      raise
