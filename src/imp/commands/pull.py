import typer

from imp import console, git, workflow

def pull (
   merge: bool = typer.Option (False, "--merge", help="Integrate with a merge commit instead of rebasing"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide AI conflict resolution"),
   favor_ours: bool = typer.Option (False, "--ours", help="Bias AI toward our branch on conflicts"),
   favor_theirs: bool = typer.Option (False, "--theirs", help="Bias AI toward their branch on conflicts"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Auto-accept AI conflict resolutions (non-interactive)"),
):
   """Fetch and integrate upstream into the current branch, auto-resolving conflicts.

   Mirrors git pull, but when the branches have diverged the rebase (or
   --merge) replays and any conflicts flow straight into imp's AI resolve step
   instead of stopping you. Does not push — that's imp push, or imp sync to do
   both.
   """

   if favor_ours and favor_theirs:
      console.fatal ("Cannot use --ours and --theirs together")

   git.require ()
   git.require_clean ("imp commit first")

   console.header ("Pull")

   b = git.branch ()
   if not b:
      console.fatal ("Detached HEAD; checkout a branch first")

   if not git.has_upstream ():
      console.hint (f"git push -u origin {b}")
      console.fatal ("No upstream branch")

   console.label ("Branch")
   console.item (b)
   console.out.print ()

   console.spin ("Fetching...", git.fetch)

   behind = git.count_behind ()
   ahead = git.count_ahead ()

   if behind == 0:
      console.success ("Already up to date")
      raise typer.Exit (0)

   if ahead > 0:
      console.label ("Diverged")
      console.item (f"{ahead} ahead, {behind} behind")
   else:
      console.label ("Behind")
      console.item (f"{behind} commits")
   console.out.print ()

   strategy = "merge" if merge else "rebase"
   console.muted (f"{'Merging' if merge else 'Rebasing'} onto upstream...")

   workflow.integrate (
      "@{u}",
      strategy=strategy,
      whisper=whisper,
      favor_ours=favor_ours,
      favor_theirs=favor_theirs,
      auto=yes,
   )

   console.success ("Up to date")
   console.hint ("imp push to publish, or imp sync to pull and push")
