import re
from typing import Annotated, Any

import typer

from imp_git import approval, console, features, git, plans, state, workspace

_TICKET = re.compile (r"^[A-Za-z]+-[0-9]+$")


def _members (repos: list [str] | None) -> tuple [str, list [tuple [str, str]]]:
   if repos:
      value = workspace.here ()
      if not value:
         raise state.StateError ("No repositories found here")
      return str (value ["name"]), [ workspace.match (value, alias) for alias in repos ]
   git.require ()
   return git.repo_name (), [ (git.repo_name (), git.repo_root ()) ]


def _plan (name: str, ticket: str, scope_name: str, members: list [tuple [str, str]]) -> dict [str, Any]:
   order = [ alias for alias, _ in members ]
   span = order if len (members) > 1 else None
   children = []
   blockers = []
   warnings = []
   for alias, repository in members:
      with workspace.inside (repository):
         child = features.plan_start (name, ticket=ticket, span=span)
      blockers.extend (f"{alias}: {reason}" for reason in child ["blockers"])
      warnings.extend (f"{alias}: {reason}" for reason in child ["warnings"])
      children.append ({ "alias": alias, "repository": repository, "plan": child })
   return plans.build (
      "start",
      str (children [0] ["plan"] ["payload"] ["name"]),
      scope={ "workspace": scope_name },
      items=[
         { "action": "start", "alias": child ["alias"], "branch": child ["plan"] ["payload"] ["branch"] }
         for child in children
      ],
      payload_schema="imp.start-plan.v3",
      payload={
         "name": children [0] ["plan"] ["payload"] ["name"],
         "ticket": ticket.upper (),
         "span": order if span else [],
         "members": children,
      },
      blockers=blockers,
      warnings=warnings,
   )


def _apply (plan: dict [str, Any]) -> dict [str, Any]:
   """Create every member in order, unwinding completely if one fails."""

   created: list [dict [str, Any]] = []
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
               features.discard (str (member ["branch"]), str (member ["path"]))
         except Exception:
            stranded.append (str (member ["path"]))
      if stranded:
         raise state.StateError (f"{error}; could not unwind {', '.join (stranded)}") from error
      raise

   return {
      "name": plan ["payload"] ["name"],
      "ticket": plan ["payload"] ["ticket"],
      "span": plan ["payload"] ["span"],
      "members": created,
   }


def _show (plan: dict [str, Any]):
   console.header (f"Start feature: {plan ['label']}")
   console.table (
      [ "Repository", "Branch", "Base", "Worktree" ],
      [
         [
            str (child ["alias"]),
            str (child ["plan"] ["payload"] ["branch"]),
            f"{child ['plan'] ['payload'] ['base:ref']} ({str (child ['plan'] ['payload'] ['base:oid']) [:10]})",
            str (child ["plan"] ["payload"] ["path"]),
         ]
         for child in plan ["payload"] ["members"]
      ],
   )
   for blocker in plan ["blockers"]:
      console.err (str (blocker))


def _success (data: dict [str, Any]):
   members = data ["members"]
   if len (members) == 1:
      console.success (f"Feature ready: {data ['name']}")
      console.hint (f"cd {members [0] ['path']}")
      return
   console.success (f"Feature ready across {len (members)} repositories")
   for member in members:
      console.item (f"{member ['alias']}: {member ['path']}")


def start (
   name: Annotated [str, typer.Argument (help="Readable feature name; becomes feature/<name>")] = "",
   repos: Annotated [
      list [str] | None,
      typer.Option (
         "--repo",
         help="Workspace repository to span; repeat per repository. "
              "The order given is the order they integrate at done time",
      ),
   ] = None,
   ticket: Annotated [
      str,
      typer.Option (
         "--ticket",
         help="Ticket ID such as SPK-12345; prefixes the branch (feature/SPK-12345-<name>) "
              "and flows into commit subjects",
      ),
   ] = "",
):
   """Create an isolated feature: one branch plus one worktree, based on fresh trunk.

   The worktree lands under ~/.worktrees/<repo>/<name> (override with `git config
   imp.worktrees <dir>`), so the current checkout is never disturbed. The branch bases
   on origin's trunk, or on local trunk when it only leads the remote.

   Spanning: run from a directory of checkouts with repeated --repo flags to create
   one feature across several repositories. The order you name them is recorded as
   `imp.span.<name>.order` in each member and replayed dependency-first by `imp done`.

   Nothing is written outside Git: the feature IS the branch and its worktree.
   Deterministic; sends nothing to AI.
   """

   if not name:
      console.fatal ("Feature name is required")
   if ticket and not _TICKET.fullmatch (ticket):
      console.fatal ("Ticket must look like SPK-12345")
   try:
      scope_name, members = _members (repos)
      plan = _plan (name, ticket, scope_name, members)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   return approval.run (
      plan,
      noun="start",
      confirm="Create this feature?",
      result_schema="imp.start.v2",
      apply=_apply,
      show=_show,
      success=_success,
   )
