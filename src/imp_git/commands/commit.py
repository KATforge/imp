from typing import Annotated

import typer

from imp_git import (
   approval,
   commit_plan,
   console,
   features,
   git,
   identity,
   runtime,
   state,
   validate,
)


def _show (plan: dict):
   console.header ("Commit plan")
   payload = plan ["payload"]
   console.table ([ "Commit", "Files" ], [[ str (payload ["message"]), str (len (payload ["paths"])) ]])
   for warning in plan.get ("warnings", []):
      console.warn (str (warning))
   for blocker in plan.get ("blockers", []):
      console.err (str (blocker))


def _manual (message: str, actor: str) -> dict:
   features.assert_write_access (actor)
   if not validate.commit (message):
      console.fatal ("Message must use Conventional Commits")
   if not git.staged_files ():
      console.fatal ("Nothing staged")
   git.commit (message)
   data = { "branch": git.branch (), "message": message, "oid": git.rev_parse ("HEAD") }
   if runtime.options.json:
      from imp_git import result

      result.emit ("imp.commit.v1", "imp commit", data, json_output=True)
   else:
      console.success (f"Committed: {message}")
   return data


def _planned (
   *,
   actor: str,
   dry_run: bool,
   json_output: bool,
   yes: bool,
) -> dict:
   try:
      plan = commit_plan.create (actor_id=actor)
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
      confirm="Create this local commit?",
      plan_schema="imp.commit-plan.v3",
      result_schema="imp.commit.v1",
      apply=apply_plan,
      show=_show,
      success=success,
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
   )


def commit (
   message: Annotated [str, typer.Option ("--message", "-m", help="Commit staged changes without AI")] = "",
):
   """Create one local commit. Sends the selected diff to AI unless -m is used."""

   actor_id = runtime.options.actor_id
   dry_run = runtime.options.dry_run
   json_output = runtime.options.json
   yes = runtime.options.yes

   git.require ()
   actor = identity.actor (actor_id)
   if message:
      return _manual (message, actor)
   return _planned (
      actor=actor,
      dry_run=dry_run,
      json_output=json_output,
      yes=yes,
   )
