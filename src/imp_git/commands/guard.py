from typing import Annotated

import typer

from imp_git import console, git, guards, identity, result, runtime

guard = typer.Typer (
   name="guard",
   help="Manage temporary, human-approved agent exceptions",
   no_args_is_help=True,
)


def _repository () -> str:
   git.require ()
   return git.repo_root ()


@guard.command ("prepare", hidden=True)
def prepare (
   capability: Annotated [str, typer.Argument ()],
   provider: Annotated [str, typer.Option ("--provider")],
   session_id: Annotated [str, typer.Option ("--session-id")],
):
   """Create the short-lived request consumed after provider approval."""

   actor_id = identity.actor ()
   expected = identity.resource ("actor", provider, session_id)
   if actor_id != expected:
      console.fatal (f"Guard request actor must be {expected}")
   try:
      value = guards.prepare (
         _repository (),
         actor_id,
         capability,
         provider=provider,
         session_id=session_id,
      )
   except guards.GuardError as error:
      console.fatal (str (error))
   return result.emit (
      "imp.guard-prepare.v1",
      "imp guard prepare",
      { "request": value },
      json_output=runtime.options.json,
   )


@guard.command ("check", hidden=True)
def check (capability: Annotated [str, typer.Argument ()]):
   """Return a live grant for the current repository and actor."""

   try:
      value = guards.active (_repository (), identity.actor (), capability)
   except guards.GuardError as error:
      console.fatal (str (error))
   return result.emit (
      "imp.guard-check.v1",
      "imp guard check",
      { "active": bool (value), "grant": value },
      json_output=runtime.options.json,
   )


@guard.command ("request")
def request (
   capability: Annotated [str, typer.Argument (help="Exception to request, currently direct-edit")],
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
):
   """Request human-approved direct editing for 30 minutes."""

   repository = _repository ()
   actor_id = identity.actor ()
   if actor_id.startswith ("actor:human:") and not runtime.options.actor_id:
      actor_id = ""
   try:
      value = guards.grant (repository, actor_id, capability)
   except guards.GuardError as error:
      console.fatal (f"{error}. Ask the agent to request this exception and approve its provider prompt.")
   data = { "grant": value }
   if json_output or runtime.options.json:
      return result.emit ("imp.guard.v1", "imp guard request", data, json_output=True)
   console.success (f"Temporary {capability} access approved")
   console.item (f"Repository: {repository}")
   console.item (f"Actor: {value ['actor_id']}")
   console.item (f"Expires: {value ['expires_at']}")
   return data


@guard.command ("status")
def status (
   all_repositories: Annotated [bool, typer.Option ("--all", help="Show grants for every repository")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
):
   """Show live temporary grants."""

   repository = "" if all_repositories else _repository ()
   try:
      values = guards.list_ (repository)
   except guards.GuardError as error:
      console.fatal (str (error))
   data = { "grants": values }
   if json_output or runtime.options.json:
      return result.emit ("imp.guards.v1", "imp guard status", data, json_output=True)
   if not values:
      console.muted ("No temporary guard access")
      return data
   console.table (
      [ "Capability", "Actor", "Repository", "Expires" ],
      [
         [
            str (value ["capability"]),
            str (value ["actor_id"]),
            str (value ["repository"]),
            str (value ["expires_at"]),
         ]
         for value in values
      ],
   )
   return data


@guard.command ("revoke")
def revoke (
   capability: Annotated [str, typer.Argument (help="Exception to revoke")] = "direct-edit",
   all_repositories: Annotated [bool, typer.Option ("--all", help="Revoke this session across repositories")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
):
   """Revoke temporary access immediately."""

   repository = "" if all_repositories else _repository ()
   actor_id = identity.actor ()
   if actor_id.startswith ("actor:human:") and not runtime.options.actor_id:
      actor_id = ""
   try:
      removed = guards.revoke (repository, actor_id, capability)
   except guards.GuardError as error:
      console.fatal (str (error))
   data = { "capability": capability, "num_revoked": removed }
   if json_output or runtime.options.json:
      return result.emit ("imp.guard-revoke.v1", "imp guard revoke", data, json_output=True)
   console.success (f"Revoked {removed} temporary guard record{'s' if removed != 1 else ''}")
   return data
