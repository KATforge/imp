from typing import Annotated

import typer

from imp_git import commit_plan, console, features, git, identity, plans, repo, result, runtime, state, validate


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


def commit (
   all: Annotated [bool, typer.Option ("--all", "-a", help="Include every dirty path")] = False,
   exclude: Annotated [list [str] | None, typer.Option ("--exclude", "-E", help="Exclude matching paths")] = None,
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the exact displayed plan")] = False,
   push: Annotated [bool, typer.Option ("--push", "-p", hidden=True)] = False,
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
):
   """Plan and create approved local Conventional Commits."""

   git.require ()
   actor = identity.actor (actor_id)
   yes = yes or runtime.options.yes
   if push:
      console.fatal ("imp commit never pushes; run imp push after committing")
   if amend and fixup:
      console.fatal ("--amend and --fixup are mutually exclusive")
   if list_plans:
      return _list_plans (json_output)
   if fixup:
      if apply or plan_only or all or single or message:
         console.fatal ("--fixup cannot be combined with other commit modes")
      target = "HEAD" if fixup == "__pick__" else fixup
      if git.published (target):
         console.fatal ("Cannot create a fixup for published history")
      features.assert_write_access (actor)
      if not git.staged_files ():
         console.fatal ("Nothing staged")
      git.commit_fixup (target)
      data = { "branch": git.branch (), "oid": git.rev_parse ("HEAD"), "target": target }
      if json_output or runtime.options.json:
         result.emit ("imp.commit.v1", "imp commit --fixup", data, json_output=True)
      else:
         console.success (f"Created fixup for {target}")
      return data
   if message:
      if apply or plan_only or all or single:
         console.fatal ("imp commit -m cannot be combined with planning options")
      features.assert_write_access (actor)
      if amend and git.published ("HEAD"):
         console.fatal ("Cannot amend published history")
      if not validate.commit (message, int (repo.get ("commit:max_subject", 72))):
         console.fatal ("Message must use Conventional Commits")
      if not git.staged_files ():
         console.fatal ("Nothing staged")
      git.commit (message, amend=amend)
      data = { "branch": git.branch (), "message": message, "oid": git.rev_parse ("HEAD") }
      if json_output or runtime.options.json:
         result.emit ("imp.commit.v1", "imp commit", data, json_output=True)
      else:
         console.success (f"Committed: {message}")
      return data

   try:
      if apply:
         plan = plans.resolve ("commit", "" if apply == "__pick__" else apply)
      else:
         plan = commit_plan.create (
            actor_id=actor,
            all_changes=all,
            amend=amend,
            exclude=exclude,
            single=single,
            staged=staged,
            whisper=whisper,
            persist=not (dry_run or runtime.options.dry_run),
         )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   machine = json_output or runtime.options.json
   if not machine:
      _show (plan)
   if plan_only or dry_run or runtime.options.dry_run:
      if machine:
         result.emit ("imp.commit-plan.v1", "imp commit", { "plan": plan }, json_output=True)
      return plan
   if plan.get ("state") != "ready":
      console.fatal ("Commit plan is blocked")
   if runtime.options.no_input and not yes:
      console.fatal ("Non-interactive commit requires --plan or --apply <plan-id> --yes")
   if not yes and not console.confirm (f"Create {len (plan ['payload']['groups'])} local commit(s)?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   try:
      data = commit_plan.apply (plan, actor)
   except state.StateError as error:
      console.fatal (str (error))
   if machine:
      result.emit ("imp.commit.v1", "imp commit", data, json_output=True)
   else:
      for value in data ["commits"]:
         console.success (str (value ["message"]))
   return data
