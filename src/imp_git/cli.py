import click
from typer.core import TyperCommand, TyperGroup


def _key (parameter: click.Parameter) -> str:
   longest = [ value for value in parameter.opts if value.startswith ("--") ]
   name = (longest or parameter.opts or [ str (parameter.name) ]) [0]

   return name.lstrip ("-").lower ()


def ordered (params: list [click.Parameter]) -> list [click.Parameter]:
   """Order options alphabetically, keeping arguments positional and help last."""

   arguments = [ value for value in params if isinstance (value, click.Argument) ]
   options = [ value for value in params if not isinstance (value, click.Argument) ]
   trailing = [ value for value in options if value.name == "help" ]
   sortable = sorted ((value for value in options if value.name != "help"), key=_key)

   return arguments + sortable + trailing


class SortedCommand (TyperCommand):

   def get_params (self, ctx: click.Context) -> list [click.Parameter]:
      return ordered (super ().get_params (ctx))


class SortedGroup (TyperGroup):

   def get_params (self, ctx: click.Context) -> list [click.Parameter]:
      return ordered (super ().get_params (ctx))
