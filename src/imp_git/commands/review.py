import os
import shlex
from pathlib import Path, PurePosixPath
from typing import Annotated

import typer

from imp_git import ai, console, features, git, identity, integration, prompts, result, runtime, state, validate

_FIX = "Fix recommendations with smart AI"
_MARK = "Mark this exact candidate reviewed"
_LEAVE = "Leave unmarked"

_DIRTY_AUTOMATION = """Dirty feature requires a separately approved commit plan.

Next:
  imp -C {path} commit --all --plan
  imp -C {path} commit --apply <plan-id> --yes
  imp -C {path} review {feature_id}"""


def _direct_review (last: int, whisper: str):
   patch = git.diff_range (f"HEAD~{last}..HEAD") if last > 0 else git.diff (staged=True) or git.diff ()
   if not patch:
      console.muted ("No changes to review")
      raise typer.Exit (0)
   findings = console.spin ("Reviewing...", ai.smart, prompts.review (ai.truncate (patch), whisper), False)
   console.divider ()
   console.md (findings)
   console.divider ()
   return { "diff": patch, "findings": findings }


def _feature (value: str) -> dict | None:
   if value:
      return features.resolve (value, title="Select feature to review")
   candidates = features.eligible ()
   if not candidates:
      return None
   current = features.current ()
   labels = [ features.label (candidate) for candidate in candidates ]
   if current:
      selected = next ((
         candidate for candidate in candidates
         if candidate ["feature_id"] == current ["feature_id"]
      ), None)
      if selected:
         return selected
   if not current:
      direct = "current checkout · direct"
      if runtime.options.json or runtime.options.no_input:
         raise state.StateError ("Pass an explicit feature name or ID")
      selected = console.choose ("Select source to review", [ *labels, direct ])
      return None if selected == direct else candidates [labels.index (selected)]
   return features.pick ("Select feature to review", candidates)


def _commit_dirty (feature: dict, actor_id: str, machine: bool):
   path = str (feature ["path"])
   if git.clean_at (path):
      return
   if machine or runtime.options.no_input or runtime.options.yes:
      raise state.StateError (_DIRTY_AUTOMATION.format (
         path=shlex.quote (path),
         feature_id=feature ["feature_id"],
      ))

   from imp_git.commands.commit import commit

   claim = feature.get ("claim") or {}
   preserve_claim = claim.get ("held_by") == actor_id
   features.claim (feature, actor_id)
   previous = Path.cwd ()
   console.muted ("Feature is dirty; preparing an exact commit plan before review")
   try:
      os.chdir (path)
      commit (all=True, actor_id=actor_id)
   finally:
      os.chdir (previous)
      if not preserve_claim:
         features.release (feature, actor_id)
   if not git.clean_at (path):
      raise state.StateError ("Review requires a committed feature candidate")


def _patch_paths (patch: str) -> list [str]:
   paths = set ()
   for line in patch.splitlines ():
      if not line.startswith ("diff --git "):
         continue
      try:
         parts = shlex.split (line)
      except ValueError as error:
         raise state.StateError ("Smart AI returned an invalid patch header") from error
      if len (parts) != 4 or parts [:2] != [ "diff", "--git" ]:
         raise state.StateError ("Smart AI returned an invalid patch header")
      left, right = parts [2:]
      if not left.startswith ("a/") or not right.startswith ("b/") or left [2:] != right [2:]:
         raise state.StateError ("Smart AI fixes cannot rename files")
      path = PurePosixPath (left [2:])
      if path.is_absolute () or ".." in path.parts:
         raise state.StateError ("Smart AI patch contains an unsafe path")
      paths.add (path.as_posix ())
   return sorted (paths)


def _patch (feature: dict, plan: dict) -> tuple [str, list [str]]:
   payload = plan ["payload"]
   path = str (feature ["path"])
   parts = [git.capture (
      "-C", path, "diff", "--binary", "--no-ext-diff", "--no-renames",
      payload ["target_oid"], payload ["candidate_oid"],
   )]
   parts.append (git.capture ("-C", path, "diff", "--cached", "--binary", "--no-renames"))
   parts.append (git.capture ("-C", path, "diff", "--binary", "--no-renames"))
   untracked = [value for value in git.capture (
      "-C", path, "ls-files", "--others", "--exclude-standard", "-z"
   ).split ("\0") if value]
   for relative in untracked:
      full = Path (path) / relative
      try:
         text = full.read_text ()
      except (OSError, UnicodeDecodeError):
         parts.append (f"Binary or unreadable untracked file: {relative}\n")
         continue
      parts.append (f"diff --git a/{relative} b/{relative}\n--- /dev/null\n+++ b/{relative}\n")
      parts.append ("".join (f"+{line}" for line in text.splitlines (keepends=True)))
   patch = "\n".join (part.rstrip () for part in parts if part).rstrip () + "\n"
   return patch, _patch_paths (patch)


def _plan (feature: dict, actor_id: str) -> tuple [dict, str, list [str]]:
   plan = integration.current_plan (feature)
   if not plan or plan.get ("state") in { "applied", "stale" }:
      plan = integration.plan_done (feature, actor_id=actor_id)
   patch, files = _patch (feature, plan)
   return plan, patch, files


def _show (feature: dict, payload: dict, patch: str, file_count: int, dirty: bool):
   console.header (f"Review {feature ['name']}")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Target", f"{payload ['target_ref']} ({payload ['target_oid'] [:12]})" ],
         [ "Candidate", payload ["candidate_oid"] [:12] ],
         [ "Files", str (file_count) ],
         [ "Dirty", "yes" if dirty else "no" ],
      ],
   )
   console.out.print (patch)


def _findings (patch: str, whisper: str, no_ai: bool, machine: bool) -> tuple [str, dict [str, int]]:
   empty = { "blocker": 0, "warning": 0, "note": 0 }
   if no_ai or not patch.strip ():
      return "", empty
   text = console.spin ("Reviewing...", ai.smart, prompts.review (ai.truncate (patch), whisper), False)
   lowered = text.lower ()
   counts = { name: lowered.count (name) for name in empty }
   if not machine:
      console.divider ()
      console.md (text)
      console.divider ()
   return text, counts


def _action (
   findings: str,
   *,
   dirty: bool,
   fix: bool,
   machine: bool,
   mark_reviewed: bool,
) -> str:
   if fix:
      return "fix"
   if mark_reviewed:
      return "mark"
   if machine or dirty or not console.interactive ():
      return ""
   if findings:
      selected = console.choose ("Review action", [ _FIX, _MARK, _LEAVE ])
      return { _FIX: "fix", _MARK: "mark", _LEAVE: "" } [selected]
   return "mark" if console.confirm ("Mark this exact candidate reviewed?") else ""


def _fix (
   feature: dict,
   patch: str,
   findings: str,
   files: list [str],
   *,
   actor_id: str,
   candidate_oid: str,
   machine: bool,
) -> dict:
   prompt = prompts.review_fix (ai.truncate (patch), findings, files)
   response = ai.smart (prompt, False) if machine else console.spin ("Fixing...", ai.smart, prompt, False)
   value = ai.strip_fences (response).strip ()
   if value == "NO_CHANGES":
      if not machine:
         console.muted ("Smart AI found no safe changes to apply")
      return { "applied": False, "files": [] }
   if "GIT binary patch" in value or not validate.publishable (value):
      raise state.StateError ("Smart AI returned an unsafe patch")
   changed = _patch_paths (value)
   if not changed:
      raise state.StateError ("Smart AI did not return a unified Git patch")
   unexpected = sorted (set (changed) - set (files))
   if unexpected:
      raise state.StateError (f"Smart AI patch escaped the reviewed files: {', '.join (unexpected)}")
   features.claim (feature, actor_id)
   path = str (feature ["path"])
   head = git.run_at (path, "rev-parse", "HEAD", check=False).stdout.strip ()
   if head != candidate_oid or not git.clean_at (path):
      raise state.StateError ("Feature changed while smart AI prepared its patch")
   try:
      git.apply_at (path, value + "\n")
   except RuntimeError as error:
      raise state.StateError (str (error)) from error
   if not machine:
      console.success (f"Applied smart AI fixes to {len (changed)} file(s)")
      console.hint ("inspect, test, commit, then run imp review again")
   return { "applied": True, "files": changed }


def _mark (
   plan: dict,
   feature: dict,
   files: list [str],
   findings: dict [str, int],
   *,
   actor_id: str,
   dirty: bool,
   machine: bool,
   requested: bool,
) -> dict | None:
   should_mark = requested
   if dirty:
      if should_mark:
         console.fatal ("Commit or remove dirty feature state before marking reviewed")
      if not machine:
         console.muted ("Commit or remove dirty feature state before marking reviewed")
      return None
   if not should_mark:
      if not machine:
         console.muted ("Review left unmarked")
      return None
   return integration.mark_reviewed (plan, actor_id, files=files, findings=findings)


def _managed_review (
   feature: dict,
   *,
   actor_id: str,
   fix: bool,
   json_output: bool,
   mark_reviewed: bool,
   no_ai: bool,
   whisper: str,
) -> dict:
   if fix and no_ai:
      raise state.StateError ("--fix requires smart AI review")
   if fix and mark_reviewed:
      raise state.StateError ("--fix and review approval are mutually exclusive")
   machine = json_output or runtime.options.json
   _commit_dirty (feature, actor_id, machine)
   plan, patch, files = _plan (feature, actor_id)
   payload = plan ["payload"]
   dirty = bool (git.capture ("-C", str (feature ["path"]), "status", "--porcelain=v1"))
   if not machine:
      _show (feature, payload, patch, len (files), dirty)
   findings_text, findings = _findings (patch, whisper, no_ai, machine)
   action = _action (
      findings_text,
      dirty=dirty,
      fix=fix,
      machine=machine,
      mark_reviewed=mark_reviewed,
   )
   fixed = { "applied": False, "files": [] }
   receipt = None
   if action == "fix":
      if dirty:
         raise state.StateError ("Commit or remove dirty feature state before applying smart AI fixes")
      fixed = _fix (
         feature,
         patch,
         findings_text,
         files,
         actor_id=actor_id,
         candidate_oid=str (payload ["candidate_oid"]),
         machine=machine,
      )
      dirty = bool (fixed ["applied"])
   else:
      receipt = _mark (
         plan,
         feature,
         files,
         findings,
         actor_id=actor_id,
         dirty=dirty,
         machine=machine,
         requested=action == "mark",
      )
   data = {
      "candidate_oid": payload ["candidate_oid"],
      "diff": patch,
      "feature_id": feature ["feature_id"],
      "files": files,
      "findings": findings,
      "findings_text": findings_text,
      "fix": fixed,
      "mark_available": not dirty,
      "path": str (feature ["path"]),
      "plan_id": plan ["plan_id"],
      "receipt": receipt,
      "target_ref": payload ["target_ref"],
      "target_oid": payload ["target_oid"],
   }
   if machine:
      result.emit ("imp.review.v1", "imp review", data, json_output=True)
   elif receipt:
      console.success ("Exact candidate marked reviewed")
   return data


def review (
   feature: Annotated [str, typer.Argument (help="Managed feature name")] = "",
   fix: Annotated [bool, typer.Option ("--fix", help="Apply review recommendations with smart AI")] = False,
   no_ai: Annotated [bool, typer.Option ("--no-ai", help="Show complete deterministic review only")] = False,
   mark_reviewed: Annotated [
      bool,
      typer.Option ("--mark-reviewed", hidden=True),
   ] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
   last: Annotated [int, typer.Option ("--last", "-l", hidden=True)] = 0,
   whisper: Annotated [str, typer.Option ("--whisper", "-w", hidden=True)] = "",
):
   """Inspect all feature state before integration and optionally acknowledge it."""

   try:
      managed = _feature (feature)
      if not managed:
         if fix:
            raise state.StateError ("--fix requires a managed feature")
         return _direct_review (last, whisper)
      actor = identity.actor (actor_id)
      return _managed_review (
         managed,
         actor_id=actor,
         fix=fix,
         json_output=json_output,
         mark_reviewed=mark_reviewed,
         no_ai=no_ai,
         whisper=whisper,
      )
   except state.StateError as error:
      console.fatal (str (error))
