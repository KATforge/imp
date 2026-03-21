import typer
from rich.console import Console

from imp import __version__
from imp.commands.amend import amend
from imp.commands.branch import branch
from imp.commands.clean import clean
from imp.commands.commit import commit
from imp.commands.doctor import doctor
from imp.commands.done import done
from imp.commands.fix import fix
from imp.commands.help import help
from imp.commands.log import log
from imp.commands.pr import pr
from imp.commands.release import release
from imp.commands.revert import revert
from imp.commands.review import review
from imp.commands.split import split
from imp.commands.status import status
from imp.commands.sync import sync
from imp.commands.undo import undo

app = typer.Typer (
   name="imp",
   no_args_is_help=True,
   rich_markup_mode="rich",
   add_completion=False,
)


def _version (value: bool):
   if value:
      Console ().print (f"imp {__version__}")
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


app.command () (amend)
app.command () (branch)
app.command () (clean)
app.command () (commit)
app.command () (doctor)
app.command () (done)
app.command () (fix)
app.command () (help)
app.command () (log)
app.command () (pr)
app.command () (release)
app.command () (revert)
app.command () (review)
app.command () (split)
app.command () (status)
app.command () (sync)
app.command () (undo)
