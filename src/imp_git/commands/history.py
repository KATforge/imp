import typer

from imp_git import ai, console, git, prompts


def history (
   path: str = typer.Argument ("", help="Optional file whose history to follow"),
   count: int = typer.Option (20, "--count", "-n", help="Maximum commits to show"),
   explain: bool = typer.Option (False, "--explain", "-e", help="Append an AI history narrative"),
):
   """Show repository or file history, with an optional AI narrative."""

   git.require ()
   if count < 1:
      console.fatal ("Count must be at least 1")

   log = git.log_history (path, count, color=console.out.is_terminal)
   if not log:
      console.muted ("No history found")
      raise typer.Exit (0)

   console.out.print (log, markup=False, highlight=False)
   if not explain:
      return

   patches = git.log_history_patches (path, min (count, 10)) if path else ""
   summary = console.spin (
      "Reading history...",
      ai.smart,
      prompts.history (log, ai.truncate (patches), path),
   )

   console.out.print ()
   console.label ("AI narrative")
   console.md (summary)
