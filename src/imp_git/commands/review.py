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
   fix: Annotated [bool, typer.Option ("--fix", "-f", hidden=True)] = False,
   dangerous: Annotated [bool, typer.Option ("--dangerous", "-d", hidden=True)] = False,
):
   """Inspect all feature state before integration and optionally acknowledge it."""

   del fix, dangerous
   try:
      managed = _feature (feature)
   except state.StateError as error:
      console.fatal (str (error))
   if not managed:
      return _direct_review (last, whisper)
   try:
      plan = integration.current_plan (managed)
      if not plan or plan.get ("state") in { "applied", "stale" }:
         plan = integration.plan_done (managed, actor_id=identity.actor (actor_id))
      patch, files = _patch (managed, plan)
   except state.StateError as error:
      console.fatal (str (error))

   payload = plan ["payload"]
   findings_text = ""
   counts = { "blocker": 0, "warning": 0, "note": 0 }
   machine = json_output or runtime.options.json
   if not machine:
      console.header (f"Review {managed ['name']}")
      console.table (
         [ "Field", "Value" ],
         [
            [ "Target", f"{payload ['target_ref']} ({payload ['target_oid'] [:12]})" ],
            [ "Candidate", payload ["candidate_oid"] [:12] ],
            [ "Files", str (len (files)) ],
            [ "Dirty", "yes" if git.capture ("-C", str (managed ["path"]), "status", "--porcelain=v1") else "no" ],
         ],
      )
      console.out.print (patch)
   if not no_ai and patch.strip ():
      findings_text = console.spin (
         "Reviewing...", ai.smart, prompts.review (ai.truncate (patch), whisper), False
      )
      lowered = findings_text.lower ()
      counts = {
         "blocker": lowered.count ("blocker"),
         "warning": lowered.count ("warning"),
         "note": lowered.count ("note"),
      }
      if not machine:
         console.divider ()
         console.md (findings_text)
         console.divider ()

   dirty = bool (git.capture ("-C", str (managed ["path"]), "status", "--porcelain=v1"))
   receipt = None
   should_mark = mark_reviewed
   if not machine and not mark_reviewed and not dirty and console.interactive ():
      should_mark = console.confirm ("Mark this exact candidate reviewed?")
   if not machine and not dirty and not should_mark:
      console.muted ("Review left unmarked")
   if not machine and dirty:
      console.muted ("Commit or remove dirty feature state before marking reviewed")
   if should_mark:
      if dirty:
         console.fatal ("Commit or remove dirty feature state before marking reviewed")
      try:
         receipt = integration.mark_reviewed (plan, identity.actor (actor_id), files=files, findings=counts)
      except state.StateError as error:
         console.fatal (str (error))
   data = {
      "candidate_oid": payload ["candidate_oid"],
      "diff": patch,
      "feature_id": managed ["feature_id"],
      "files": files,
      "findings": counts,
      "findings_text": findings_text,
      "mark_available": not dirty,
      "path": str (managed ["path"]),
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
