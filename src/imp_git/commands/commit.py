from typing import Annotated

import typer

from imp_git import (
   approval,
   commit_plan,
   console,
   features,
   git,
   identity,
   plans,
   repo,
   result,
   runtime,
   state,
   validate,
)


def _show (plan: dict):
   console.header ("Commit plan")
   groups = plan.get ("payload", {}).get ("groups", [])
   if groups:
      rows = [
         [ str (index), str (group ["message"]), str (len (group ["files"])) ]
         for index, group in enumerate (groups, start=1)
      ]
      console.table ([ "#", "Commit", "Files" ], rows, right={ 0, 2 })
   for warning in plan.get ("warnings", []):
      console.warn (str (warning))
   for blocker in plan.get ("blockers", []):
      console.err (str (blocker))


def _list_plans (json_output: bool):
   values = plans.all ("commit")
   if json_output or runtime.options.json:
      return result.emit ("imp.plans.v1", "imp commit --plans", { "plans": values }, json_output=True)

   console.header ("Commit plans")
   if not values:
      console.muted ("No commit plans")
      return { "plans": [] }
   console.table (
      [ "State", "Plan", "Created" ],
      [ [ str (plan ["state"]), str (plan ["label"]), str (plan ["created_at"]) ] for plan in values ],
   )
   return { "plans": values }


def _finish (data: dict, command: str, message: str, json_output: bool) -> dict:
   if json_output or runtime.options.json:
      result.emit ("imp.commit.v1", command, data, json_output=True)
   else:
      console.success (message)
   return data


def _fixup (ref: str, actor: str, json_output: bool) -> dict:
   target = "HEAD" if ref == "__pick__" else ref
   if git.published (target):
      console.fatal ("Cannot create a fixup for published history")
   features.assert_write_access (actor)
   if not git.staged_files ():
      console.fatal ("Nothing staged")
   git.commit_fixup (target)
   data = { "branch": git.branch (), "oid": git.rev_parse ("HEAD"), "target": target }
   return _finish (data, "imp commit --fixup", f"Created fixup for {target}", json_output)


def _manual (message: str, actor: str, amend: bool, push: bool, json_output: bool) -> dict:
   features.assert_write_access (actor)
   if amend and git.published ("HEAD"):
      console.fatal ("Cannot amend published history")
   if not validate.commit (message, int (repo.get ("commit:max_subject", 72))):
      console.fatal ("Message must use Conventional Commits")
   if not git.staged_files ():
      console.fatal ("Nothing staged")
   git.commit (message, amend=amend)
   if push:
      git.push_current ()
   data = { "branch": git.branch (), "message": message, "oid": git.rev_parse ("HEAD"), "pushed": push }
   return _finish (data, "imp commit", f"Committed: {message}", json_output)


def _planned (
   *,
   actor: str,
   all_changes: bool,
   amend: bool,
   apply: str,
   dry_run: bool,
   exclude: list [str] | None,
   json_output: bool,
   plan_only: bool,
   push: bool,
   single: bool,
   staged: bool,
   whisper: str,
   yes: bool,
) -> dict:
   try:
      plan = plans.resolve ("commit", "" if apply == "__pick__" else apply) if apply else commit_plan.create (
         actor_id=actor,
         all_changes=all_changes,
         amend=amend,
         exclude=exclude,
         single=single,
         staged=staged,
         whisper=whisper,
         persist=not dry_run,
      )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   def apply_plan (value: dict) -> dict:
      data = commit_plan.apply (value, actor)
      if push:
         git.push_current ()
      return { **data, "pushed": push }

   def success (data: dict):
      for value in data ["commits"]:
         console.success (str (value ["message"]))
      if data ["pushed"]:
         console.success (f"Pushed {data ['branch']}")

   return approval.run (
      plan,
      command="imp commit",
      noun="commit",
      confirm=f"Create {len (plan ['payload'] ['groups'])} local commit(s){' and push' if push else ''}?",
      plan_schema="imp.commit-plan.v2",
      result_schema="imp.commit.v1",
      apply=apply_plan,
      show=_show,
      success=success,
      plan_only=plan_only,
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
   )


def commit (
   all: Annotated [bool, typer.Option ("--all", "-a", help="Include every dirty path")] = False,
   exclude: Annotated [list [str] | None, typer.Option ("--exclude", "-E", help="Exclude matching paths")] = None,
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the exact displayed plan")] = False,
   whisper: Annotated [str, typer.Option ("--whisper", "-w", help="Context for commit planning")] = "",
   message: Annotated [str, typer.Option ("--message", "-m", help="Commit staged changes without AI")] = "",
   staged: Annotated [bool, typer.Option ("--staged", help="Plan only staged changes")] = False,
   single: Annotated [bool, typer.Option ("--single", help="Force one logical commit")] = False,
   plan_only: Annotated [bool, typer.Option ("--plan", help="Persist the plan without applying it")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply one saved commit plan")] = "",
   list_plans: Annotated [bool, typer.Option ("--plans", help="List saved commit plans")] = False,
   dry_run: Annotated [bool, typer.Option ("--dry-run", help="Display an ephemeral plan")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit a versioned JSON result")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
   amend: Annotated [bool, typer.Option ("--amend", help="Replace the last unpublished commit")] = False,
   fixup: Annotated [str, typer.Option ("--fixup", help="Create a fixup commit for an unpublished ref")] = "",
   push: Annotated [bool, typer.Option ("--push", "-p", help="Push after committing")] = False,
):
   """Plan and create approved local Conventional Commits."""

   git.require ()
   actor = identity.actor (actor_id)
   yes = yes or runtime.options.yes
   if amend and fixup:
      console.fatal ("--amend and --fixup are mutually exclusive")
   if list_plans:
      return _list_plans (json_output)
   if fixup:
      if apply or plan_only or all or single or message or push:
         console.fatal ("--fixup cannot be combined with other commit modes")
      return _fixup (fixup, actor, json_output)
   if message:
      if apply or plan_only or all or single:
         console.fatal ("imp commit -m cannot be combined with planning options")
      return _manual (message, actor, amend, push, json_output)
   dry_run = dry_run or runtime.options.dry_run
   if push and (plan_only or dry_run):
      console.fatal ("--push cannot be combined with --plan or --dry-run")
   return _planned (
      actor=actor,
      all_changes=all,
      amend=amend,
      apply=apply,
      dry_run=dry_run,
      exclude=exclude,
      json_output=json_output,
      plan_only=plan_only,
      push=push,
      single=single,
      staged=staged,
      whisper=whisper,
      yes=yes,
   )
