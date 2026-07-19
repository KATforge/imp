import typer

from imp import __version__
from imp import console
from imp.commands.amend import amend
from imp.commands.branch import branch
from imp.commands.changelog import changelog
from imp.commands.clean import clean
from imp.commands.collapse import collapse
from imp.commands.commit import commit
from imp.commands.config import configure
from imp.commands.docs import docs
from imp.commands.doctor import doctor
from imp.commands.done import done
from imp.commands.explain import explain
from imp.commands.fix import fix
from imp.commands.fixup import fixup
from imp.commands.fleet import fleet
from imp.commands.help import help
from imp.commands.init import init
from imp.commands.log import log
from imp.commands.merge import merge
from imp.commands.pr import pr
from imp.commands.pull import pull
from imp.commands.push import push
from imp.commands.release import release
from imp.commands.rescue import rescue
from imp.commands.resolve import resolve
from imp.commands.revert import revert
from imp.commands.review import review
from imp.commands.setup import setup
from imp.commands.ship import ship
from imp.commands.split import split
from imp.commands.standup import standup
from imp.commands.stash import stash
from imp.commands.status import status
from imp.commands.sync import sync
from imp.commands.tag import tag
from imp.commands.tidy import tidy
from imp.commands.undo import undo
from imp.commands.update import update
from imp.commands.version import version as version_cmd
from imp.commands.worktree import worktree

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
   amend, branch, changelog, clean, collapse, commit,
   docs, doctor, done, explain, fix, fixup, fleet, help,
   init, log, merge, pr, pull, push, release, rescue, resolve,
   revert, review, setup, ship, split, standup,
   status, sync, tag, tidy, undo, update,
]

for _cmd in _commands:
   app.command () (_cmd)

app.command ("config") (configure)
app.command ("version") (version_cmd)
app.add_typer (stash, name="stash")
app.add_typer (worktree, name="worktree")
