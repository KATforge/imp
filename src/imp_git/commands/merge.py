import typer

from imp_git import console, git, workflow


def merge (
   source: str = typer.Argument (..., help="Branch to merge in"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Skip confirmation"),
   no_ff: bool = typer.Option (True, "--no-ff/--ff", help="Force a merge commit (default), or allow fast-forward"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide AI conflict resolution"),
   favor_ours: bool = typer.Option (False, "--ours", help="Bias AI toward our branch on conflicts"),
   favor_theirs: bool = typer.Option (False, "--theirs", help="Bias AI toward their branch on conflicts"),
   auto: bool = typer.Option (False, "--auto", help="Auto-accept all AI conflict resolutions"),
):
   """Merge a branch into the current branch, with AI conflict resolution.

   Merges <source> into the current branch. On conflicts, walks each file
   through the same flow as imp resolve and then finalizes the merge commit.
   Both branches are kept.
   """

   if favor_ours and favor_theirs:
      console.fatal ("Cannot use --ours and --theirs together")

   git.require ()
   git.require_clean ("imp commit first")

   current = git.branch ()
   if not current:
      console.fatal ("Detached HEAD; checkout a branch first")

   if source == current:
      console.fatal (f"Already on {source}")

   ref = source
   if not git.rev_parse (ref):
      if git.remote_has_branch (source):
         console.muted (f"No local {source}; fetching...")
         git.fetch ()
         ref = f"origin/{source}"
         if not git.rev_parse (ref):
            console.fatal (f"Branch {source} not found after fetch")
      else:
         console.fatal (f"Branch {source} does not exist")

   console.header ("Merge")

   console.label (f"{source} → {current}")
   console.item ("Fast-forward allowed" if not no_ff else "Force merge commit (--no-ff)")
   console.out.print ()

   if not yes and not console.confirm ("Proceed?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   workflow.integrate (
      ref,
      strategy="merge",
      no_ff=no_ff,
      whisper=whisper,
      favor_ours=favor_ours,
      favor_theirs=favor_theirs,
      auto=auto,
   )

   console.success (f"Merged {source} into {current}")
