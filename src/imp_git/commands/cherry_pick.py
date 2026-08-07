import typer

from imp_git import ai, console, git, prompts
from imp_git.commands.resolve import resolve


def cherry_pick (
   ref: str = typer.Argument (..., help="Commit to apply"),
   explain: bool = typer.Option (False, "--explain", "-e", help="Explain the commit before applying it"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Apply without confirmation"),
   favor_ours: bool = typer.Option (False, "--ours", help="Bias AI conflict resolution toward this branch"),
   favor_theirs: bool = typer.Option (False, "--theirs", help="Bias AI conflict resolution toward the commit"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide AI"),
):
   """Preview and apply a commit, with optional explanation and AI conflict resolution."""

   git.require ()
   git.require_clean ("commit or stash first")

   if favor_ours and favor_theirs:
      console.fatal ("Cannot use --ours and --theirs together")
   if not git.ref_exists (ref):
      console.fatal (f"Cannot resolve commit: {ref}")

   console.header ("Cherry-pick")
   shown = git.show_raw (ref, stat=True, color=console.out.is_terminal)
   console.out.print (shown, markup=False, highlight=False)

   if explain:
      summary = console.spin (
         "Explaining...",
         ai.smart,
         prompts.explain (ai.truncate (git.show_patch (ref)), "balanced", whisper),
      )
      console.out.print ()
      console.label ("AI summary")
      console.md (summary)

   if not yes and not console.confirm (f"Apply {git.rev_parse_short (ref)}?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   if git.cherry_pick_start (ref):
      console.success ("Cherry-picked")
      return

   if not git.cherry_pick_in_progress ():
      console.fatal ("Cherry-pick failed before entering conflict resolution")

   console.warn (f"{len (git.conflicts ())} conflict(s); handing off to resolve")
   resolve (
      whisper=whisper,
      favor_ours=favor_ours,
      favor_theirs=favor_theirs,
      yes=yes,
   )

   remaining = git.conflicts ()
   if remaining:
      console.hint ("imp resolve to continue, or imp cherry-pick --abort")
      console.fatal (f"{len (remaining)} conflict(s) still unresolved")

   if not git.cherry_pick_continue ():
      console.fatal ("Could not finalize cherry-pick")

   console.success ("Cherry-picked after resolving conflicts")
