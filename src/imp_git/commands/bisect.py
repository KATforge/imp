import shlex

import typer

from imp_git import ai, console, git, passthrough, prompts


def bisect (
   bad: str = typer.Argument (..., help="Known bad commit"),
   good: str = typer.Argument (..., help="Known good commit"),
   command: str = typer.Option (..., "--run", "-r", help="Command whose zero exit means good"),
   explain: bool = typer.Option (False, "--explain", "-e", help="Explain the first bad commit"),
):
   """Run an automated bisect and optionally explain the first bad commit."""

   git.require ()
   git.require_clean ("commit or stash first")

   if not git.ref_exists (bad):
      console.fatal (f"Cannot resolve bad commit: {bad}")
   if not git.ref_exists (good):
      console.fatal (f"Cannot resolve good commit: {good}")

   args = shlex.split (command)
   if not args:
      console.fatal ("--run command cannot be empty")

   console.header ("Bisect")
   if passthrough.run ([ "bisect", "start", bad, good ]) != 0:
      console.fatal ("Could not start bisect")

   suspect = ""
   try:
      code = passthrough.run ([ "bisect", "run", *args ])
      suspect = git.rev_parse ("refs/bisect/bad")
      if code != 0 or not suspect:
         console.fatal ("Bisect did not identify a first bad commit")

      console.label ("First bad commit")
      console.item (git.show_oneline (suspect))

      if explain:
         summary = console.spin (
            "Explaining suspect...",
            ai.smart,
            prompts.explain (ai.truncate (git.show_patch (suspect)), "balanced"),
         )
         console.out.print ()
         console.md (summary)
   finally:
      passthrough.run ([ "bisect", "reset" ])

   console.hint (f"imp show {suspect} --explain")
