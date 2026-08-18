from typing import Annotated

import typer

from imp_git import (
   approval,
   commit_plan,
   console,
   features,
   git,
   identity,
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


def _finish (data: dict, command: str, message: str, json_output: bool) -> dict:
   if json_output:
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


def _manual (message: str, actor: str, amend: bool, json_output: bool) -> dict:
   features.assert_write_access (actor)
   if amend and git.published ("HEAD"):
      console.fatal ("Cannot amend published history")
   if not validate.commit (message, int (repo.get ("commit:max_subject", 72))):
      console.fatal ("Message must use Conventional Commits")
   if not git.staged_files ():
      console.fatal ("Nothing staged")
   git.commit (message, amend=amend)
   data = { "branch": git.branch (), "message": message, "oid": git.rev_parse ("HEAD") }
   return _finish (data, "imp commit", f"Committed: {message}", json_output)


def _planned (
   *,
   actor: str,
   all_changes: bool,
   amend: bool,
   dry_run: bool,
   exclude: list [str] | None,
   json_output: bool,
   whisper: str,
   yes: bool,
) -> dict:
   try:
      plan = commit_plan.create (
         actor_id=actor,
         all_changes=all_changes,
         amend=amend,
         exclude=exclude,
         whisper=whisper,
      )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   def apply_plan (value: dict) -> dict:
      return commit_plan.apply (value, actor)

   def success (data: dict):
      for value in data ["commits"]:
         console.success (str (value ["message"]))

   return approval.run (
      plan,
      command="imp commit",
      noun="commit",
      confirm=f"Create {len (plan ['payload'] ['groups'])} local commit(s)?",
      plan_schema="imp.commit-plan.v2",
      result_schema="imp.commit.v1",
      apply=apply_plan,
      show=_show,
      success=success,
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
   )


def commit (
   all: Annotated [bool, typer.Option ("--all", "-a", help="Include every dirty path")] = False,
   exclude: Annotated [list [str] | None, typer.Option ("--exclude", "-E", help="Exclude matching paths")] = None,
   whisper: Annotated [str, typer.Option ("--whisper", "-w", help="Context for commit planning")] = "",
   message: Annotated [str, typer.Option ("--message", "-m", help="Commit staged changes without AI")] = "",
   amend: Annotated [bool, typer.Option ("--amend", help="Replace the last unpublished commit")] = False,
   fixup: Annotated [str, typer.Option ("--fixup", help="Create a fixup commit for an unpublished ref")] = "",
):
   """Plan and create approved local Conventional Commits."""

   actor_id = runtime.options.actor_id
   dry_run = runtime.options.dry_run
   json_output = runtime.options.json
   yes = runtime.options.yes

   git.require ()
   actor = identity.actor (actor_id)
   if amend and fixup:
      console.fatal ("--amend and --fixup are mutually exclusive")
   if fixup:
      return _fixup (fixup, actor, json_output)
   if message:
      return _manual (message, actor, amend, json_output)
   return _planned (
      actor=actor,
      all_changes=all,
      amend=amend,
      dry_run=dry_run,
      exclude=exclude,
      json_output=json_output,
      whisper=whisper,
      yes=yes,
   )
