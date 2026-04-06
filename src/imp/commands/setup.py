from pathlib import Path

import typer

from imp import ai, console, git, prompts


def _add_remote (url: str):
   existing = git.remote_url ()

   if existing == url:
      console.muted ("Origin already set")
      return

   if existing:
      choice = console.choose (
         f"Origin is {existing}, replace?",
         [ "Yes", "No" ],
      )

      if choice == "No":
         return

      git.remote_set_url (url)
      console.success (f"Updated origin → {url}")
   else:
      git.remote_add (url)
      console.success (f"Added origin → {url}")


def _scan_files () -> str:
   entries = sorted (p.name for p in Path.cwd ().iterdir () if not p.name.startswith ("."))
   return "\n".join (entries)


def _setup_gitignore (files: str):
   path = Path (".gitignore")
   existing = path.read_text ().strip () if path.exists () else ""

   result = ai.fast (prompts.gitignore (files, existing))
   result = result.strip ()

   if not result or result == "NONE":
      console.muted ("No new .gitignore entries needed")
      return

   if existing:
      combined = existing + "\n" + result + "\n"
   else:
      combined = result + "\n"

   path.write_text (combined)
   console.success ("Updated .gitignore")


def setup (
   url: str = typer.Argument (help="GitHub repository URL"),
):
   """Initialize a git repo with remote and .gitignore."""

   console.header ("Setup")

   if git.is_repo ():
      console.muted ("Already a git repository")
   else:
      git.init ()
      console.success ("Initialized git repository")

   _add_remote (url)

   files = _scan_files ()

   if files:
      _setup_gitignore (files)
   else:
      console.muted ("Empty directory, skipping .gitignore")

   console.out.print ()
   console.success ("Done")
