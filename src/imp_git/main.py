import json
import os
import sys
import traceback
from pathlib import Path
from typing import Annotated

import click
import typer
from typer.core import TyperGroup

from imp_git import __version__, console, passthrough, runtime
from imp_git.commands.commit import commit
from imp_git.commands.config import config_app
from imp_git.commands.doctor import doctor
from imp_git.commands.done import done
from imp_git.commands.fleet import fleet
from imp_git.commands.recover import recover
from imp_git.commands.review import review
from imp_git.commands.ship import ship
from imp_git.commands.start import start
from imp_git.commands.status import status
from imp_git.commands.worktree import worktree


class GitGroup (TyperGroup):

   def get_command (self, ctx: click.Context, cmd_name: str) -> click.Command | None:
      command = super ().get_command (ctx, cmd_name)
      if command:
         return command

      @click.pass_context
      def invoke (command_ctx: click.Context):
         code = passthrough.run ([ cmd_name, *command_ctx.args ])
         raise click.exceptions.Exit (code)

      return click.Command (
         cmd_name,
         callback=invoke,
         add_help_option=False,
         context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
         },
      )


app = typer.Typer (
   name="imp",
   cls=GitGroup,
   no_args_is_help=True,
   rich_markup_mode="rich",
   add_completion=False,
)

def _version (value: bool):
   if value:
      console.out.print (f"imp {__version__}")
      raise typer.Exit ()

@app.callback ()
def main (
   ctx: typer.Context,
   version: bool | None = typer.Option (
      None,
      "--version", "-v",
      help="Show version and exit",
      callback=_version,
      is_eager=True,
   ),
   repo_path: Annotated [str, typer.Option ("-C", "--repo", help="Run against this repository")] = "",
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
   dry_run: Annotated [bool, typer.Option ("--dry-run", help="Display an ephemeral plan")] = False,
   no_input: Annotated [bool, typer.Option ("--no-input", help="Fail instead of prompting")] = False,
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply an exact displayed plan")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
   ascii_output: Annotated [bool, typer.Option ("--ascii", help="Use plain ASCII output")] = False,
   no_color: Annotated [bool, typer.Option ("--no-color", help="Disable terminal color")] = False,
):
   """[green]imp[/green] — safe Git workstreams for people and agents"""

   if repo_path:
      target = Path (repo_path).expanduser ().resolve ()
      if not target.is_dir ():
         raise click.UsageError (f"Repository path does not exist: {target}")
      os.chdir (target)

   runtime.configure (
      actor_id=actor_id,
      ascii=ascii_output,
      command=ctx.invoked_subcommand or "",
      dry_run=dry_run,
      json=json_output,
      no_input=no_input,
      no_color=no_color,
      repo=repo_path,
      yes=yes,
   )
   console.out.no_color = no_color

_commands = [
   commit, doctor, done, fleet, recover,
   review, ship, start, status,
]

for _cmd in _commands:
   app.command () (_cmd)

app.add_typer (config_app, name="config")
app.add_typer (worktree, name="worktree")

_NATIVE = { command.name or command.callback.__name__ for command in app.registered_commands }
_NATIVE.update ({ "config", "worktree" })


def _native_request (args: list [str]) -> bool:
   """Return whether argv targets Imp's documented native surface."""

   index = 0
   while index < len (args):
      value = args [index]
      if value in { "-C", "--repo", "--actor-id" }:
         index += 2
         continue
      if value in { "--ascii", "--dry-run", "--json", "--no-color", "--no-input", "--yes", "-y" }:
         index += 1
         continue
      if value.startswith ("-"):
         return False
      return value in _NATIVE
   return False


def _optional_values (args: list [str]) -> list [str]:
   """Give optional-value flags a sentinel understood by native commands."""

   values = list (args)
   for index, value in enumerate (values):
      if value not in { "--apply", "--fixup" }:
         continue
      if index + 1 == len (values) or values [index + 1].startswith ("-"):
         values [index] = f"{value}=__pick__"
   return values


def _fail (error: Exception) -> int:
   """Report one uncaught failure as a versioned envelope or concise line."""

   if os.environ.get ("IMP_DEBUG"):
      traceback.print_exc ()
   subcommand = next ((value for value in sys.argv [1:] if not value.startswith ("-")), "")
   if runtime.options.json or "--json" in sys.argv [1:]:
      sys.stdout.write (json.dumps ({
         "schema": "imp.error.v1",
         "command": f"imp {subcommand}".strip (),
         "ok": False,
         "error": { "message": str (error), "type": type (error).__name__ },
         "data": {},
         "warnings": [],
      }, indent=3, sort_keys=True) + "\n")
      return 1

   console.err (f"imp failed: {error}")
   console.hint ("set IMP_DEBUG=1 for a full traceback")
   return 1


def run () -> int:
   """Run Imp, falling back to Git when native syntax does not match."""

   sys.argv [1:] = _optional_values (sys.argv [1:])
   try:
      outcome = app (standalone_mode=False)
   except click.UsageError as error:
      args = sys.argv [1:]
      if args and not _native_request (args):
         return passthrough.run (args)

      error.show ()
      return error.exit_code
   except click.ClickException as error:
      error.show ()
      return error.exit_code
   except click.exceptions.Exit as error:
      return error.exit_code
   except Exception as error:
      return _fail (error)

   if isinstance (outcome, int):
      return outcome

   return 0
