from typing import Annotated, Any

import typer

from imp_git import (
   ai,
   approval,
   commit_plan,
   console,
   features,
   git,
   plans,
   result,
   roster,
   runtime,
   state,
   workspace,
)
from imp_git.commands import done as done_command


def _member_diff (member: dict [str, Any]) -> str:
   trunk = str (member ["target"])
   branch = str (member ["branch"])
   base = git.merge_base (trunk, branch)
   committed = git.capture ("diff", base, branch) if base else git.capture ("diff", branch)
   dirty = ""
   if member ["path"]:
      dirty = git.run_at (str (member ["path"]), "diff", "HEAD", check=False).stdout
      untracked = git.run_at (
         str (member ["path"]), "ls-files", "--others", "--exclude-standard", check=False,
      ).stdout.splitlines ()
      dirty += "".join (f"\nnew untracked file: {path}" for path in untracked if path)
   return f"### {member ['alias']} ({branch})\n{committed}{dirty}"


def _entry_diff (entry: dict [str, Any]) -> str:
   parts = []
   for member in entry ["members"]:
      with workspace.inside (str (member ["repository"])):
         parts.append (_member_diff (member))
   return "\n".join (parts)


def _has_changes (diff: str) -> bool:
   if "new untracked file:" in diff:
      return True
   return any (
      line.startswith (("+", "-")) and not line.startswith (("+++", "---"))
      for line in diff.splitlines ()
   )


def _judged (entry: dict [str, Any]) -> dict [str, Any]:
   diff = _entry_diff (entry)
   if not _has_changes (diff):
      return { **entry, "verdict": "discard", "reason": "No changes against trunk" }
   try:
      value = ai.verdict (str (entry ["name"]), str (entry ["age"]), diff)
   except state.StateError as error:
      return { **entry, "verdict": "hold", "reason": str (error) }
   verdict = str (value.get ("verdict", "hold"))
   if verdict not in { "integrate", "discard", "hold" }:
      verdict = "hold"
   return { **entry, "verdict": verdict, "reason": str (value.get ("reason", "")) }


def _commit_dirty (member: dict [str, Any]):
   if not member ["path"]:
      return
   with workspace.inside (str (member ["path"])):
      if not git.status_short ():
         return
      commit_plan.apply (commit_plan.create ())


def _integrate (entry: dict [str, Any], workspace_name: str):
   for member in entry ["members"]:
      _commit_dirty (member)
   plan = done_command._plan_group (str (entry ["name"]), workspace_name, [ entry ])
   if plan ["blockers"]:
      raise state.StateError ("; ".join (str (value) for value in plan ["blockers"]))
   done_command._apply_group (plan)


def _discard (entry: dict [str, Any]) -> list [str]:
   refs = []
   for member in entry ["members"]:
      _commit_dirty (member)
      with workspace.inside (str (member ["repository"])):
         refs.append (features.to_attic (str (member ["branch"])))
         features.discard (str (member ["branch"]), str (member ["path"]))
   return [ ref for ref in refs if ref ]


def _apply (plan: dict [str, Any]) -> dict [str, Any]:
   payload = plan ["payload"]
   workspace_name = str (payload ["workspace"])
   integrated = []
   discarded = []
   held = [
      { "feature": entry ["name"], "reason": entry ["reason"] }
      for entry in payload ["entries"] if entry ["verdict"] == "hold"
   ]
   for entry in payload ["entries"]:
      if entry ["verdict"] == "integrate":
         try:
            _integrate (entry, workspace_name)
            integrated.append (str (entry ["name"]))
         except (state.StateError, typer.Exit) as error:
            held.append ({ "feature": entry ["name"], "reason": str (error) or "Integration was blocked" })
   for entry in payload ["entries"]:
      if entry ["verdict"] == "discard":
         try:
            refs = _discard (entry)
            discarded.append ({ "feature": entry ["name"], "attic": refs })
         except (state.StateError, typer.Exit) as error:
            held.append ({ "feature": entry ["name"], "reason": str (error) or "Discard was blocked" })
   expired = _expire (payload ["repositories"])
   plans.mark (plan, "applied", applied_at=state.now ())
   return {
      "attic_expired": expired,
      "discarded": discarded,
      "held": held,
      "integrated": integrated,
      "kept": payload ["kept"],
   }


def _expire (repositories: list [str]) -> list [str]:
   expired = []
   for repository in repositories:
      with workspace.inside (repository):
         expired.extend (features.expire_attic ())
   return expired


def _show (plan: dict [str, Any]):
   console.header (f"Cleanup: {plan ['scope'] ['workspace']}")
   console.table (
      [ "Feature", "Repositories", "Age", "Verdict", "Reason" ],
      [
         [
            str (entry ["name"]),
            " ".join (entry ["repositories"]),
            str (entry ["age"]),
            str (entry ["verdict"]),
            str (entry ["reason"]),
         ]
         for entry in plan ["payload"] ["entries"]
      ],
   )
   console.muted ("integrate runs the project checks; discard parks the branch tip in the attic for 30 days")


def _success (data: dict [str, Any]):
   console.success (
      f"Flat: {len (data ['integrated'])} integrated, {len (data ['discarded'])} discarded, "
      f"{len (data ['held'])} held"
   )
   for value in data ["held"]:
      console.warn (f"held {value ['feature']}: {value ['reason']}")


def cleanup (
   keep: Annotated [
      list [str] | None,
      typer.Option ("--keep", help="Feature to leave untouched; repeat as needed"),
   ] = None,
):
   """Reconcile every open feature with AI and flatten the workspace.

   Each open feature's full difference against trunk, including uncommitted work, is
   judged by AI as integrate, discard, or hold. The verdict table is shown for approval
   before anything happens. Integrations commit outstanding work, run the project
   checks, and land dependency-first exactly like `imp done`; discards park the branch
   tip under refs/imp/attic for 30 days before deletion, so a wrong verdict is
   recoverable with `git branch <name> <attic-ref>`. Holds are left in place and
   reported: flat with exceptions beats flat at all costs.

   The outcome is a workspace with no feature branches and no feature worktrees beyond
   holds and --keep exemptions. Attic refs past 30 days are purged on every run. Sends
   each feature's diff to AI for the verdict and for any work-in-progress commit messages.
   """

   value = workspace.here ()
   if not value:
      console.fatal ("No repository here")
   kept = { features.name_of (name) for name in (keep or []) }
   entries = roster.collect (value)
   pending = [ entry for entry in entries if entry ["name"] not in kept ]
   repositories = sorted (workspace.repositories (value).values ())
   if not pending:
      expired = _expire (repositories)
      data = {
         "attic_expired": expired, "discarded": [], "held": [],
         "integrated": [], "kept": sorted (kept),
      }
      if runtime.options.json:
         return result.emit ("imp.cleanup.v1", "imp cleanup", data, json_output=True)
      console.success ("Already flat")
      return data
   judged = [
      _judged (entry) if runtime.options.json
      else console.spin (f"Judging {entry ['name']}...", _judged, entry)
      for entry in pending
   ]
   plan = plans.build (
      "cleanup",
      str (value ["name"]),
      scope={ "workspace": str (value ["name"]) },
      items=[
         { "action": entry ["verdict"], "feature": entry ["name"] }
         for entry in judged
      ],
      payload_schema="imp.cleanup-plan.v1",
      payload={
         "entries": judged,
         "kept": sorted (kept),
         "repositories": repositories,
         "workspace": str (value ["name"]),
      },
   )
   return approval.run (
      plan,
      noun="cleanup",
      confirm="Apply these verdicts?",
      result_schema="imp.cleanup.v1",
      apply=_apply,
      show=_show,
      success=_success,
      destructive=True,
   )
