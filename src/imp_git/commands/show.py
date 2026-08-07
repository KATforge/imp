import typer

from imp_git import ai, console, git, prompts


def show (
   ref: str = typer.Argument ("HEAD", help="Commit or object to show"),
   stat: bool = typer.Option (False, "--stat", help="Show file statistics"),
   name_only: bool = typer.Option (False, "--name-only", help="Show changed paths"),
   explain: bool = typer.Option (False, "--explain", "-e", help="Append an AI explanation"),
   brief: bool = typer.Option (False, "--brief", "-b", help="Use a brief AI explanation"),
   full: bool = typer.Option (False, "--full", "-f", help="Use a detailed AI explanation"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the explanation"),
):
   """Show a Git object immediately, with an optional AI explanation."""

   git.require ()

   if stat and name_only:
      console.fatal ("--stat and --name-only are mutually exclusive")
   if brief and full:
      console.fatal ("--brief and --full are mutually exclusive")

   explain = explain or brief or full
   color = console.out.is_terminal and not name_only
   shown = git.show_raw (ref, stat=stat, name_only=name_only, color=color)

   if not shown:
      console.muted ("Nothing to show")
      raise typer.Exit (0)

   console.out.print (shown, markup=False, highlight=False)
   if not explain:
      return

   patch = git.show_patch (ref)
   mode = "brief" if brief else "full" if full else "balanced"
   summary = console.spin (
      "Explaining...",
      ai.smart,
      prompts.explain (ai.truncate (patch), mode, whisper),
   )

   console.out.print ()
   console.label ("AI summary")
   console.md (summary)
