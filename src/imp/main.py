import typer

from imp import __version__
from imp import console
from imp.commands.amend import amend
from imp.commands.branch import branch
from imp.commands.changelog import changelog
from imp.commands.clean import clean
from imp.commands.commit import commit
from imp.commands.config import configure
from imp.commands.doctor import doctor
from imp.commands.done import done
from imp.commands.fix import fix
from imp.commands.help import help
from imp.commands.log import log
from imp.commands.pr import pr
from imp.commands.push import push
from imp.commands.release import release
from imp.commands.resolve import resolve
from imp.commands.revert import revert
from imp.commands.review import review
from imp.commands.setup import setup
from imp.commands.ship import ship
from imp.commands.split import split
from imp.commands.status import status
from imp.commands.sync import sync
from imp.commands.tidy import tidy
from imp.commands.undo import undo

app = typer.Typer (
   name="imp",
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
   version: bool | None = typer.Option (
      None,
      "--version", "-v",
      help="Show version and exit",
      callback=_version,
      is_eager=True,
   ),
):
   """[green]imp[/green] — AI-powered git workflow"""


_commands = [
   amend, branch, changelog, clean, commit,
   doctor, done, fix, help, log,
   pr, push, release, resolve, revert,
   review, setup, ship, split, status,
   sync, tidy, undo,
]

for _cmd in _commands:
   app.command () (_cmd)

app.command ("config") (configure)
