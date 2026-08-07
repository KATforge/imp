import typer

from imp_git import commit_plan, console, git, passthrough


def _plan (files: list [str], whisper: str) -> list [dict]:
   return commit_plan.groups_for_paths (files, whisper=whisper)


def add (
   paths: list [str] | None = typer.Argument (None, help="Paths to stage directly"),
   all: bool = typer.Option (False, "--all", "-A", help="Stage every change without AI grouping"),
   patch: bool = typer.Option (False, "--patch", "-p", help="Use Git's interactive hunk selector"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide AI grouping"),
):
   """Stage paths, hunks, or AI-proposed logical groups.

   Explicit paths stage directly. --patch opens Git's hunk selector. With no
   arguments, AI groups every changed file by intent and presents a checklist.
   """

   git.require ()
   paths = paths or []

   if sum ([ bool (paths), all, patch ]) > 1:
      console.fatal ("Paths, --all, and --patch are mutually exclusive")

   if patch:
      raise typer.Exit (passthrough.run ([ "add", "--patch" ]))

   if all:
      git.stage ()
      console.success ("Staged every change")
      return

   if paths:
      git.add (paths)
      console.success (f"Staged {len (paths)} path(s)")
      return

   files = git.diff_names ()
   if not files:
      console.muted ("No changes to stage")
      raise typer.Exit (0)

   console.header ("Add")
   groups = _plan (files, whisper)
   labels = [ f"{group ['message']}  ({len (group ['files'])} files)" for group in groups ]
   selected = console.check ("Stage groups", labels, selected=labels)

   chosen = [
      path
      for label, group in zip (labels, groups, strict=True)
      if label in selected
      for path in group ["files"]
   ]

   if not chosen:
      console.muted ("Nothing selected")
      raise typer.Exit (0)

   git.add (chosen)
   console.success (f"Staged {len (chosen)} file(s) in {len (selected)} group(s)")
   console.hint ("imp diff --staged to review")
