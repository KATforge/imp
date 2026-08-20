import sys
from collections.abc import Callable
from typing import Any, NoReturn, TypeVar

import questionary
import typer
from prompt_toolkit.styles import Style as PTStyle
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme as RichTheme

from imp_git import result, runtime
from imp_git.theme import theme

T = TypeVar ("T")

_rich_theme = RichTheme ({
   "accent": f"bold {theme.accent}",
   "success": theme.success,
   "error": f"bold {theme.error}",
   "warning": theme.warning,
   "muted": theme.muted,
   "highlight": theme.highlight,
})

out = Console (theme=_rich_theme)

_pt_style = PTStyle ([
   ("qmark", theme.accent),
   ("question", f"bold {theme.accent}"),
   ("pointer", f"bold {theme.highlight}"),
   ("highlighted", f"bold {theme.highlight}"),
   ("selected", theme.accent),
   ("answer", f"bold {theme.accent}"),
])

def header (title: str):
   out.print ()
   out.print (f"[accent]{title}[/accent]")
   out.print ()

def label (text: str):
   out.print (f"[{theme.accent}]{text}[/{theme.accent}]")

def item (text: str):
   out.print (f"  [muted]{text}[/muted]")

def items (title: str, data: str):
   label (title)
   for line in data.splitlines ():
      if line.strip ():
         item (line)

def divider ():
   out.print (
      "[muted]────────────────────────────────────────[/muted]"
   )

def raw (text: str):
   """Print verbatim content, such as a diff, without interpreting rich markup."""

   out.print (Text (text))

def table (headers: list [str], rows: list [list [str]], *, right: set [int] | None = None):
   """Render one shared responsive CLI table."""

   border = box.ROUNDED
   value = Table (box=border, header_style="accent", border_style=theme.muted, show_lines=False)
   right = right or set ()
   for index, header in enumerate (headers):
      value.add_column (header, justify="right" if index in right else "left")
   for row in rows:
      value.add_row (*row)
   out.print (value)

def success (msg: str):
   out.print (f"[success]✓[/success] {msg}")

def err (msg: str):
   out.print (Panel (
      msg,
      border_style=theme.error,
      title="Error",
      title_align="left",
   ))

def fatal (msg: str) -> NoReturn:
   if runtime.options.json:
      command = f"imp {runtime.options.command}".strip ()
      result.emit ("imp.error.v1", command, { "message": msg }, ok=False, json_output=True)
   else:
      err (msg)
   raise typer.Exit (1)

def warn (msg: str):
   out.print (f"[warning]{msg}[/warning]")

def hint (msg: str):
   out.print ()
   out.print (f"[muted]→ {msg}[/muted]")

def muted (msg: str):
   out.print (f"[muted]{msg}[/muted]")

def md (text: str):
   out.print (Markdown (text.strip ()))

def confirm (msg: str) -> bool:
   return choose (msg, [ "Yes", "No" ]) == "Yes"


def _noninteractive () -> bool:
   """Return whether prompting is unavailable, refused up front, or machine-driven."""

   if runtime.options.json or runtime.options.no_input:
      return True
   try:
      return not sys.stdin.isatty ()
   except (ValueError, OSError):
      return True

def interactive () -> bool:
   return not _noninteractive ()

def choose (title: str, options: list [str]) -> str:
   if _noninteractive ():
      fatal (f"Cannot prompt for '{title}'; name the choice explicitly, or pass --yes to approve")

   result = questionary.select (
      title,
      choices=options,
      style=_pt_style,
      qmark="▸",
      pointer="▸",
      use_arrow_keys=True,
      use_jk_keys=False,
   ).ask ()

   if result is None:
      muted ("Cancelled")
      raise typer.Exit (0)

   return result

def ask (title: str) -> str:
   """Read one free-form line, or return empty when prompting is unavailable."""

   if _noninteractive ():
      return ""
   value = questionary.text (title, style=_pt_style, qmark="▸").ask ()
   return (value or "").strip ()

def spin (title: str, fn: Callable [..., T], *args: Any, **kwargs: Any) -> T:
   with out.status (f"[accent]{title}[/accent]", spinner="dots"):
      return fn (*args, **kwargs)
