from typing import Annotated

import typer

from imp_git import config, console, fingerprint, identity, plans, repo, runtime, state

config_app = typer.Typer (name="config", help="Read, validate, and migrate Imp configuration")


def _configure ():
   cfg = config.load ()
   provider = console.choose ("AI provider", [ "claude", "ollama" ])
   models = [ "haiku", "sonnet", "opus" ] if provider == "claude" else [ "llama3.2", "mistral", "custom" ]
   fast = console.choose ("Fast model", models)
   smart = console.choose ("Smart model", models)
   cfg.update ({ "model:fast": fast, "model:smart": smart, "provider": provider })
   config.save (cfg)
   console.success ("Saved machine configuration")


@config_app.callback (invoke_without_command=True)
def configure (ctx: typer.Context):
   """Open machine configuration when no subcommand is supplied."""

   if ctx.invoked_subcommand is None:
      _configure ()


@config_app.command ("show")
def show ():
   """Show repository policy and machine defaults."""

   console.header ("Repository policy")
   console.table ([ "Key", "Value" ], [ [ key, str (value) ] for key, value in sorted (repo.load ().items ()) ])
   console.header ("Machine defaults")
   console.table ([ "Key", "Value" ], [ [ key, str (value) ] for key, value in sorted (config.load ().items ()) ])


@config_app.command ("validate")
def validate ():
   """Validate known configuration schemas and value shapes."""

   policy = repo.load ()
   machine = config.load ()
   if (policy.get ("schema") or "v0") not in { "v0", "imp.config.v1" }:
      console.fatal ("Unsupported repository configuration schema")
   if machine.get ("schema") != "imp.machine.v1":
      console.fatal ("Unsupported machine configuration schema")
   console.success ("Configuration is valid")


def _migration_plan (actor_id: str, persist: bool) -> dict:
   policy = repo.load ()
   schema = str (policy.get ("schema") or "v0")
   if schema == "imp.config.v1":
      raise state.StateError ("Repository policy already uses imp.config.v1")
   if schema != "v0":
      raise state.StateError (f"Unsupported repository configuration schema: {schema}")
   proposed = { **policy, "schema": "imp.config.v1" }
   return plans.create (
      "config-migrate",
      repo.path ().parent.name,
      scope={ "path": str (repo.path ()) },
      items=[ { "action": "add_schema", "from": "v0", "to": "imp.config.v1" } ],
      fingerprint=fingerprint.values ({ "content": repo.path ().read_text () }),
      payload_schema="imp.config-migration-plan.v1",
      payload={ "actor_id": actor_id, "policy": proposed },
      persist=persist,
   )


def _apply_migration (plan: dict, actor_id: str) -> dict:
   if plan.get ("state") != "ready" or plan.get ("payload_schema") != "imp.config-migration-plan.v1":
      raise state.StateError ("Unsupported or unavailable configuration migration plan")
   if plan ["payload"].get ("actor_id") != actor_id:
      raise state.StateError (f"Configuration migration plan belongs to {plan ['payload'].get ('actor_id')}")
   current = fingerprint.values ({ "content": repo.path ().read_text () })
   if current != plan.get ("fingerprint"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Configuration migration plan is stale")
   with state.lock ("config"):
      repo.save (dict (plan ["payload"] ["policy"]))
      if repo.load ().get ("schema") != "imp.config.v1":
         raise state.StateError ("Configuration migration validation failed")
      plans.mark (plan, "applied", applied_at=state.now ())
   return { "path": str (repo.path ()), "schema": "imp.config.v1" }


@config_app.command ("migrate")
def migrate (
   plan_only: Annotated [bool, typer.Option ("--plan", help="Persist without applying")] = False,
   apply: Annotated [str, typer.Option ("--apply", help="Apply a saved plan")] = "",
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply the displayed plan")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Add the current schema to legacy committed repository policy."""

   actor = identity.actor (actor_id)
   yes = yes or runtime.options.yes
   try:
      plan_ref = "" if apply == "__pick__" else apply
      plan = plans.resolve ("config-migrate", plan_ref) if apply else _migration_plan (
         actor,
         persist=not runtime.options.dry_run,
      )
   except state.StateError as error:
      console.fatal (str (error))
   console.table ([ "From", "To", "Path" ], [ [ "v0", "imp.config.v1", str (repo.path ()) ] ])
   if plan_only or runtime.options.dry_run:
      return plan
   if runtime.options.no_input and not yes:
      console.fatal ("Non-interactive migration requires --apply <plan-id> --yes")
   if not yes and not console.confirm ("Migrate committed repository policy?"):
      raise typer.Exit (0)
   try:
      data = _apply_migration (plan, actor)
   except state.StateError as error:
      console.fatal (str (error))
   console.success ("Repository policy migrated")
   return data
