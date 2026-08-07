import typer

from imp_git import ai, console, git, prompts


def _target (target: str, paths: list [str]) -> tuple [str, list [str]]:
   if not target:
      return "", paths

   if ".." in target or git.ref_exists (target):
      return target, paths

   return "", [ target, *paths ]


def diff (
   target: str = typer.Argument ("", help="Commit, range, or path; default: working tree"),
   paths: list [str] | None = typer.Argument (None, help="Paths to limit the diff"),
   staged: bool = typer.Option (False, "--staged", "-s", help="Show staged changes"),
   stat: bool = typer.Option (False, "--stat", help="Show file statistics instead of the patch"),
   name_only: bool = typer.Option (False, "--name-only", help="Show changed paths only"),
   explain: bool = typer.Option (False, "--explain", "-e", help="Append AI insight, which is already the default"),
   no_ai: bool = typer.Option (False, "--no-ai", "--no-explain", help="Show changes without AI insight"),
   brief: bool = typer.Option (False, "--brief", "-b", help="Use a brief AI explanation"),
   full: bool = typer.Option (False, "--full", "-f", help="Use a detailed AI explanation"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI explanation"),
):
   """Show changes immediately, then append AI insight.

   Defaults to tracked and untracked working-tree changes. Pass a commit, range,
   or path, use --staged for the index, and use --no-ai to skip the AI summary.
   """

   git.require ()

   if stat and name_only:
      console.fatal ("--stat and --name-only are mutually exclusive")
   if brief and full:
      console.fatal ("--brief and --full are mutually exclusive")

   explain = not no_ai or explain or brief or full
   ref, selected = _target (target, paths or [])
   color = console.out.is_terminal and not stat and not name_only

   tracked = git.diff (
      staged=staged,
      ref=ref,
      paths=selected,
      stat=stat,
      name_only=name_only,
      color=color,
   )
   untracked = ""
   if not staged and not ref:
      untracked = git.diff_untracked (
         selected,
         stat=stat,
         name_only=name_only,
         color=color,
      )

   shown = "\n".join (part.rstrip () for part in [ tracked, untracked ] if part)

   if not shown:
      console.muted ("No changes")
      raise typer.Exit (0)

   if console.out.is_terminal:
      console.header ("Diff")

   console.out.print (shown.rstrip (), markup=False, highlight=False)

   if not explain:
      return

   patch = "\n".join (part for part in [ untracked, tracked ] if part)
   if stat or name_only:
      tracked_patch = git.diff (staged=staged, ref=ref, paths=selected)
      untracked_patch = git.diff_untracked (selected) if not staged and not ref else ""
      patch = "\n".join (part for part in [ untracked_patch, tracked_patch ] if part)

   mode = "brief" if brief else "full" if full else "balanced"
   summary = console.spin (
      "Explaining...",
      ai.smart,
      prompts.explain (ai.truncate (patch), mode, whisper),
   )

   console.out.print ()
   console.label ("AI summary")
   console.md (summary)
