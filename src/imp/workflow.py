from collections.abc import Callable

import typer

from imp import console, git


def review_commit (
   msg: str,
   yes: bool,
   on_cancel: Callable [[], None] | None = None,
   **commit_kwargs,
) -> str:
   if yes:
      console.item (msg)
      git.commit (msg, **commit_kwargs)
      return msg

   choice = console.review (msg)

   if choice == "Edit":
      msg = console.edit (msg)

      if not msg.strip ():
         if on_cancel:
            on_cancel ()
         console.muted ("Empty message, cancelled")
         raise typer.Exit (0)

      git.commit (msg, **commit_kwargs)
   elif choice == "Yes":
      git.commit (msg, **commit_kwargs)
   else:
      if on_cancel:
         on_cancel ()
      console.muted ("Cancelled")
      raise typer.Exit (0)

   return msg
