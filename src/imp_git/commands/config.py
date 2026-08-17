import typer

from imp_git import config, console, repo
from imp_git.cli import SortedCommand

config_app = typer.Typer (name="config", help="Read and validate Imp configuration")


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


@config_app.command ("show", cls=SortedCommand)
def show ():
   """Show repository policy and machine defaults."""

   console.header ("Repository policy")
   console.table ([ "Key", "Value" ], [ [ key, str (value) ] for key, value in sorted (repo.load ().items ()) ])
   console.header ("Machine defaults")
   console.table ([ "Key", "Value" ], [ [ key, str (value) ] for key, value in sorted (config.load ().items ()) ])


@config_app.command ("validate", cls=SortedCommand)
def validate ():
   """Validate repository policy and machine configuration."""

   repo.load ()
   machine = config.load ()
   if machine.get ("schema") != "imp.machine.v1":
      console.fatal ("Unsupported machine configuration schema")
   console.success ("Configuration is valid")
