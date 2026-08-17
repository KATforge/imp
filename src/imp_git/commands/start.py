from typing import Annotated

import typer

from imp_git import approval, console, features, identity, plans, result, runtime, spans, state, workspace


def _show (plan: dict):
   payload = plan ["payload"]
   console.header ("Start feature")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Feature", str (payload ["name"]) ],
         [ "Branch", str (payload ["branch"]) ],
         [ "Base", f"{payload ['base:ref']} ({str (payload ['base:oid']) [:10]})" ],
         [ "Worktree", str (payload ["path"]) ],
         [ "Writer", str (payload ["created_by"]) ],
      ],
   )


def start (
   name: Annotated [str, typer.Argument (help="Readable feature or lane name")] = "",
   task: Annotated [str, typer.Option ("--task", help="Optional working intent, not the prompt")] = "",
   base: Annotated [str, typer.Option ("--base", help="Explicit base ref")] = "",
   target: Annotated [str, typer.Option ("--target", help="Integration target branch")] = "",
   path: Annotated [str, typer.Option ("--path", help="Explicit worktree path")] = "",
   repos: Annotated [
      list [str] | None,
      typer.Option ("--repo", help="Workspace repository to span; repeat as needed"),
   ] = None,
   plan_only: Annotated [bool, typer.Option ("--plan", help="Persist the plan without applying it")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply one saved plan")] = "",
):
   """Create and claim an isolated feature worktree."""

   actor_id = runtime.options.actor_id
   dry_run = runtime.options.dry_run
   json_output = runtime.options.json
   no_input = runtime.options.no_input
   yes = runtime.options.yes


   if repos:
      return _span (name, repos, actor_id=identity.actor (actor_id), base=base, target=target, dry_run=dry_run)

   try:
      if apply:
         plan = plans.resolve ("start", "" if apply == "__pick__" else apply)
      else:
         if not name:
            raise state.StateError ("Feature name is required")
         plan = features.plan_start (
            name,
            actor_id=identity.actor (actor_id),
            base=base,
            path=path,
            task=task,
            target=target,
            persist=not dry_run,
         )
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   def _success (feature: dict):
      console.success (f"Feature ready: {feature ['name']}")
      console.hint (f"cd {feature ['path']}")

   return approval.run (
      plan,
      command="imp start",
      noun="start",
      confirm="Create this feature?",
      plan_schema="imp.start-plan.v1",
      result_schema="imp.start.v1",
      apply=features.apply_start,
      show=_show,
      success=_success,
      plan_only=plan_only,
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
      no_input=no_input,
      wrap="feature",
   )


def _span (
   name: str,
   repos: list [str],
   *,
   actor_id: str,
   base: str,
   target: str,
   dry_run: bool,
):
   """Create one feature across several workspace repositories at once."""

   try:
      value = workspace.require ()
      selected = workspace.order (value, repos)
      members = { alias: workspace.resolve (value, alias) for alias in selected }
      if spans.find (value, name):
         raise state.StateError (f"Feature already spans repositories: {name}")
      created = []
      for alias in selected:
         with spans.inside (members [alias]):
            plan = features.plan_start (
               name, actor_id=actor_id, base=base, target=target, persist=not dry_run,
            )
            created.append ({ "alias": alias, **features.apply_start (plan) })
      span = spans.record (value, name, members, actor_id)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   data = { "span": span, "features": created }
   if runtime.options.json:
      return result.emit ("imp.span.v1", "imp start", data, json_output=True)

   console.header (f"Feature ready: {span ['name']}")
   console.table (
      [ "Repository", "Branch", "Worktree" ],
      [ [ str (value ["alias"]), str (value ["branch"]), str (value ["path"]) ] for value in created ],
   )
   return data
