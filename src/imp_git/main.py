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
from imp_git.cli import SortedCommand, ordered
from imp_git.commands.cleanup import cleanup
from imp_git.commands.commit import commit
from imp_git.commands.doctor import doctor
from imp_git.commands.done import done
from imp_git.commands.pr import pr
from imp_git.commands.release import release
from imp_git.commands.review import review
from imp_git.commands.start import start
from imp_git.commands.status import status
from imp_git.commands.worktree import worktree


class GitGroup (TyperGroup):

   def get_params (self, ctx: click.Context) -> list [click.Parameter]:
      return ordered (super ().get_params (ctx))

   def parse_args (self, ctx: click.Context, args: list [str]) -> list [str]:
      return super ().parse_args (ctx, _hoist_global (args) if _native_request (args) else args)

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
   repo_path: Annotated [str, typer.Option ("-C", help="Run against this repository")] = "",
   json_output: Annotated [bool, typer.Option ("--json", help="Emit versioned JSON")] = False,
   dry_run: Annotated [bool, typer.Option ("--dry-run", help="Display an ephemeral plan")] = False,
   no_input: Annotated [bool, typer.Option ("--no-input", help="Fail instead of prompting")] = False,
   yes: Annotated [bool, typer.Option ("--yes", "-y", help="Apply an exact displayed plan")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """[green]imp[/green] — safe Git workstreams for people and agents"""

   if repo_path:
      target = Path (repo_path).expanduser ().resolve ()
      if not target.is_dir ():
         raise click.UsageError (f"Repository path does not exist: {target}")
      os.chdir (target)

   runtime.configure (
      actor_id=actor_id,
      command=ctx.invoked_subcommand or "",
      dry_run=dry_run,
      json=json_output,
      no_input=no_input,
      repo=repo_path,
      yes=yes,
   )

_commands = [
   cleanup, commit, doctor, done, pr,
   release, review, start, status,
]

for _cmd in _commands:
   app.command (cls=SortedCommand) (_cmd)

app.add_typer (worktree, name="worktree")

_NATIVE = { command.name or command.callback.__name__ for command in app.registered_commands }
_NATIVE.update ({ "worktree" })


_GLOBAL_FLAGS = { "--dry-run", "--json", "--no-input", "--yes", "-y" }
_GLOBAL_VALUED = { "-C", "--actor-id" }


def _hoist_global (args: list [str]) -> list [str]:
   """Move global flags ahead of the subcommand so they read naturally after it.

   Click binds group options before the subcommand only, which would force
   `imp --yes done checkout`. Hoisting lets the flag sit where a person types it.
   """

   leading: list [str] = []
   rest: list [str] = []
   index = 0
   seen_command = False
   while index < len (args):
      value = args [index]
      if value in _GLOBAL_VALUED and index + 1 < len (args):
         leading.extend (args [index:index + 2])
         index += 2
         continue
      if value in _GLOBAL_FLAGS:
         leading.append (value)
         index += 1
         continue
      if not value.startswith ("-") and not seen_command:
         seen_command = True
      rest.append (value)
      index += 1

   return leading + rest if seen_command else args


def _native_request (args: list [str]) -> bool:
   """Return whether argv targets Imp's documented native surface."""

   index = 0
   while index < len (args):
      value = args [index]
      if value in _GLOBAL_VALUED:
         index += 2
         continue
      if value in _GLOBAL_FLAGS:
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
      if value != "--fixup":
         continue
      if index + 1 == len (values) or values [index + 1].startswith ("-"):
         values [index] = f"{value}=__pick__"
   return values


def _machine () -> bool:
   """Return whether this invocation asked for machine output, however far it parsed."""

   return runtime.options.json or "--json" in sys.argv [1:]


def _subcommand () -> str:
   """Return the native command from argv, skipping global flags and their values."""

   args = sys.argv [1:]
   index = 0
   while index < len (args):
      if args [index] in _GLOBAL_VALUED:
         index += 2
         continue
      if args [index].startswith ("-"):
         index += 1
         continue
      return args [index]

   return ""


def _envelope (error: Exception, *, unexpected: bool):
   """Write one versioned failure envelope, so machine clients never scrape."""

   subcommand = _subcommand ()
   value = {
      "schema": "imp.error.v1",
      "command": f"imp {subcommand}".strip (),
      "ok": False,
      "data": { "message": str (error) },
      "warnings": [],
   }
   if unexpected:
      value ["error"] = { "message": str (error), "type": type (error).__name__ }
   sys.stdout.write (json.dumps (value, indent=3, sort_keys=True) + "\n")


def _fail (error: Exception) -> int:
   """Report one uncaught failure as a versioned envelope or concise line."""

   if os.environ.get ("IMP_DEBUG"):
      traceback.print_exc ()
   if _machine ():
      _envelope (error, unexpected=True)
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

      if _machine ():
         _envelope (error, unexpected=False)
         return error.exit_code
      error.show ()
      return error.exit_code
   except click.ClickException as error:
      if _machine ():
         _envelope (error, unexpected=False)
         return error.exit_code
      error.show ()
      return error.exit_code
   except click.exceptions.Exit as error:
      return error.exit_code
   except Exception as error:
      return _fail (error)

   if isinstance (outcome, int):
      return outcome

   return 0
