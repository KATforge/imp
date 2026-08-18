from pathlib import Path
from typing import Annotated

import typer

from imp_git import approval, console, features, git, identity, plans, runtime, state, workspace


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
   base: Annotated [str, typer.Option ("--base", help="Explicit base ref")] = "",
   target: Annotated [str, typer.Option ("--target", help="Integration target branch")] = "",
   repos: Annotated [
      list [str] | None,
      typer.Option ("--repo", help="Workspace repository to span; repeat as needed"),
   ] = None,
):
   """Create and claim an isolated feature worktree."""

   actor_id = runtime.options.actor_id
   dry_run = runtime.options.dry_run
   json_output = runtime.options.json
   yes = runtime.options.yes

   if repos:
      return _span (
         name, repos, actor_id=identity.actor (actor_id), base=base, target=target,
         dry_run=dry_run, yes=yes, json_output=json_output,
      )

   git.require ()

   try:
      if not name:
         raise state.StateError ("Feature name is required")
      plan = features.plan_start (
         name,
         actor_id=identity.actor (actor_id),
         base=base,
         target=target,
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
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
      wrap="feature",
   )


def _show_span (plan: dict):
   console.header (f"Start feature: {plan ['label']}")
   console.table (
      [ "Repository", "Branch", "Worktree" ],
      [
         [
            str (member ["alias"]),
            str (member ["plan"] ["payload"] ["branch"]),
            str (member ["plan"] ["payload"] ["path"]),
         ]
         for member in plan ["payload"] ["members"]
      ],
   )
   for blocker in plan.get ("blockers", []):
      console.err (str (blocker))


def _plan_span (
   name: str,
   repos: list [str],
   *,
   actor_id: str,
   base: str,
   target: str,
) -> dict:
   """Plan one feature across several repositories, in the order the caller named."""

   if not name:
      raise state.StateError ("Feature name is required")
   value = workspace.here ()
   if not value:
      raise state.StateError (f"No repository here and none below {Path.cwd ()}")

   slug = identity.slug (name)
   members = [ workspace.match (value, alias) for alias in repos ]
   order = [ alias for alias, _ in members ]
   children = []
   blockers = []
   for alias, repository in members:
      with workspace.inside (repository):
         child = features.plan_start (
            name, actor_id=actor_id, base=base, span=order, target=target,
         )
      blockers.extend (f"{alias}: {reason}" for reason in child ["blockers"])
      children.append ({ "alias": alias, "repository": repository, "plan": child })

   return plans.build (
      "start",
      slug,
      scope={ "feature": identity.resource ("feature", slug), "workspace": value ["name"] },
      items=[
         { "action": "start", "alias": child ["alias"], "branch": child ["plan"] ["payload"] ["branch"] }
         for child in children
      ],
      payload_schema="imp.span-plan.v1",
      payload={ "name": slug, "span": order, "members": children },
      blockers=blockers,
   )


def _apply_span (plan: dict) -> dict:
   """Create every member in order, unwinding completely if one fails."""

   created: list [dict] = []
   try:
      for child in plan ["payload"] ["members"]:
         with workspace.inside (child ["repository"]):
            feature = features.apply_start (child ["plan"])
         created.append ({ "alias": child ["alias"], "repository": child ["repository"], **feature })
   except Exception as error:
      stranded = []
      for member in reversed (created):
         try:
            with workspace.inside (member ["repository"]):
               features.discard_start (member)
         except Exception:
            stranded.append (str (member ["path"]))
      if stranded:
         raise state.StateError (f"{error}; could not unwind {', '.join (stranded)}") from error
      raise

   return { "name": plan ["payload"] ["name"], "span": plan ["payload"] ["span"], "members": created }


def _span (
   name: str,
   repos: list [str],
   *,
   actor_id: str,
   base: str,
   target: str,
   dry_run: bool,
   yes: bool,
   json_output: bool,
):
   """Create one feature across several repositories, integrated in the order given."""

   try:
      plan = _plan_span (name, repos, actor_id=actor_id, base=base, target=target)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   return approval.run (
      plan,
      command="imp start",
      noun="start",
      confirm="Create this feature in every repository?",
      plan_schema="imp.span-plan.v1",
      result_schema="imp.span.v2",
      apply=_apply_span,
      show=_show_span,
      success=lambda data: console.success (
         f"Feature ready across {len (data ['members'])} repositories"
      ),
      dry_run=dry_run,
      yes=yes,
      json_output=json_output,
   )
