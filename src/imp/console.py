import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn, TypeVar

import questionary
import typer
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme as RichTheme

from imp.theme import theme

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

def review (text: str) -> str:
   panel = Panel (
      text,
      border_style=theme.accent,
      padding=(1, 2),
   )
   out.print (panel)
   out.print ()

   return choose ("Use this message?", [ "Yes", "Edit", "No" ])

def confirm (msg: str) -> bool:
   return choose (msg, [ "Yes", "No" ]) == "Yes"

def choose (title: str, options: list [str]) -> str:
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
      return options [-1]

   return result

def prompt (label: str, placeholder: str = "") -> str:
   result = questionary.text (
      label,
      default=placeholder,
      style=_pt_style,
      qmark="▸",
   ).ask ()

   return result or ""

def edit (text: str) -> str:
   import os

   editor = os.environ.get ("EDITOR", "vim")
   with tempfile.NamedTemporaryFile (
      mode="w",
      suffix=".md",
      delete=False,
   ) as f:
      f.write (text)
      path = Path (f.name)

   try:
      subprocess.run ([ editor, str (path) ], check=True)
      return path.read_text ()
   finally:
      path.unlink (missing_ok=True)

def spin (title: str, fn: Callable [..., T], *args: Any, **kwargs: Any) -> T:
   with out.status (f"[accent]{title}[/accent]", spinner="dots"):
      return fn (*args, **kwargs)
