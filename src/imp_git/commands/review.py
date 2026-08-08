from pathlib import Path
from typing import Annotated

import typer

from imp_git import ai, console, features, git, identity, integration, prompts, result, runtime, state


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
   if not current:
      direct = "current checkout · direct"
      if runtime.options.json or runtime.options.no_input:
         raise state.StateError ("Pass an explicit feature name or ID")
      selected = console.choose ("Select source to review", [ *labels, direct ])
      return None if selected == direct else candidates [labels.index (selected)]
   return features.pick ("Select feature to review", candidates)


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
   files = sorted ({
      line.removeprefix ("diff --git a/").split (" b/", 1) [0]
      for line in patch.splitlines ()
      if line.startswith ("diff --git a/")
   })
   return patch, files


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
   if not machine and not requested and not dirty and console.interactive ():
      should_mark = console.confirm ("Mark this exact candidate reviewed?")
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
   json_output: bool,
   mark_reviewed: bool,
   no_ai: bool,
   whisper: str,
) -> dict:
   plan, patch, files = _plan (feature, actor_id)
   payload = plan ["payload"]
   machine = json_output or runtime.options.json
   dirty = bool (git.capture ("-C", str (feature ["path"]), "status", "--porcelain=v1"))
   if not machine:
      _show (feature, payload, patch, len (files), dirty)
   findings_text, findings = _findings (patch, whisper, no_ai, machine)
   receipt = _mark (
      plan,
      feature,
      files,
      findings,
      actor_id=actor_id,
      dirty=dirty,
      machine=machine,
      requested=mark_reviewed,
   )
   data = {
      "candidate_oid": payload ["candidate_oid"],
      "diff": patch,
      "feature_id": feature ["feature_id"],
      "files": files,
      "findings": findings,
      "findings_text": findings_text,
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
         return _direct_review (last, whisper)
      actor = identity.actor (actor_id)
      return _managed_review (
         managed,
         actor_id=actor,
         json_output=json_output,
         mark_reviewed=mark_reviewed,
         no_ai=no_ai,
         whisper=whisper,
      )
   except state.StateError as error:
      console.fatal (str (error))
