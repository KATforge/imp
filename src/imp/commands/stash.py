import subprocess

import typer

from imp import ai, console, git, prompts

stash = typer.Typer (
   name="stash",
   help="AI-titled stash management",
   invoke_without_command=True,
   no_args_is_help=False,
)

@stash.callback ()
def _root (ctx: typer.Context):
   if ctx.invoked_subcommand is None:
      _push ()

@stash.command ("push")
def push_cmd (
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI title"),
):
   """Stash all current changes with an AI-generated title."""

   _push (whisper)

def _push (whisper: str = ""):
   git.require ()

   console.header ("Stash")

   if git.is_clean ():
      console.muted ("Nothing to stash")
      raise typer.Exit (0)

   git.stage ()
   d = git.diff (staged=True)

   if not d:
      console.muted ("No changes to stash")
      raise typer.Exit (0)

   d = ai.truncate (d)

   prompt = prompts.stash_title (d)
   if whisper:
      prompt = prompt + f"\n\nUser hint: {whisper}"

   title = ai.oneline (ai.fast (prompt))
   title = title.strip ('"').strip ("'")

   if not title:
      title = "wip"

   console.label ("Title")
   console.item (title)
   console.out.print ()

   try:
      git.stash_push (title)
   except subprocess.CalledProcessError as e:
      detail = (e.stderr or e.stdout or "").strip ()
      console.fatal (f"git stash push failed: {detail}" if detail else "git stash push failed")

   console.success ("Stashed")
   console.hint ("imp stash list, or imp stash pop to restore")

@stash.command ("list")
def list_ ():
   """List stashes with AI titles and a one-line stat summary."""

   git.require ()

   entries = git.stash_list_raw ()
   if not entries:
      console.muted ("No stashes")
      raise typer.Exit (0)

   console.header ("Stashes")

   for i, e in enumerate (entries):
      stat = git.stash_show (i, patch=False).strip ().splitlines ()
      files = len (stat)
      total_add = 0
      total_del = 0
      for line in stat:
         parts = line.split ()
         if len (parts) >= 2 and parts [0].isdigit () and parts [1].isdigit ():
            total_add += int (parts [0])
            total_del += int (parts [1])

      summary = f"{files} file(s), +{total_add} -{total_del}"
      subject = e ["subject"].split (": ", 1) [-1] if ": " in e ["subject"] else e ["subject"]

      console.label (f"[{i}] {subject}")
      console.item (f"{e ['age']} · {summary}")

@stash.command ("show")
def show (
   idx: int = typer.Argument (0, help="Stash index (default 0 = top)"),
):
   """Show the diff of a stash."""

   git.require ()

   patch = git.stash_show (idx, patch=True)
   if not patch.strip ():
      console.fatal (f"No stash at index {idx}")

   console.review (patch)

@stash.command ("pop")
def pop (
   idx: int = typer.Argument (0, help="Stash index (default 0 = top)"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Skip confirmation"),
):
   """Pop a stash back onto the working tree."""

   git.require ()

   stat = git.stash_show (idx, patch=False).strip ().splitlines ()
   if not stat:
      console.fatal (f"No stash at index {idx}")

   if not yes and len (stat) >= 10:
      console.warn (f"Stash touches {len (stat)} files")
      if not console.confirm ("Pop anyway?"):
         console.muted ("Cancelled")
         raise typer.Exit (0)

   try:
      git.stash_pop (idx)
   except subprocess.CalledProcessError as e:
      detail = (e.stderr or e.stdout or "").strip ()
      console.fatal (f"git stash pop failed: {detail}" if detail else "git stash pop failed")

   console.success (f"Popped stash@{{{idx}}}")

@stash.command ("drop")
def drop (
   idx: int = typer.Argument (0, help="Stash index (default 0 = top)"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Skip confirmation"),
):
   """Permanently discard a stash."""

   git.require ()

   stat = git.stash_show (idx, patch=False).strip ().splitlines ()
   if not stat:
      console.fatal (f"No stash at index {idx}")

   if not yes and len (stat) >= 5:
      console.warn (f"Stash touches {len (stat)} files; this cannot be undone easily")
      if not console.confirm ("Drop anyway?"):
         console.muted ("Cancelled")
         raise typer.Exit (0)

   try:
      git.stash_drop (idx)
   except subprocess.CalledProcessError as e:
      detail = (e.stderr or e.stdout or "").strip ()
      console.fatal (f"git stash drop failed: {detail}" if detail else "git stash drop failed")

   console.success (f"Dropped stash@{{{idx}}}")
