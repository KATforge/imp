import shutil
import subprocess

import typer

from imp import ai, console, git, prompts

def pr ():
   """Create a GitHub pull request with AI-generated description.

   Diffs the current branch against the base branch, then uses AI to
   generate a PR title and description. Pushes to origin if needed and
   creates the PR via the gh CLI. Requires gh to be installed.
   """

   git.require ()

   if not shutil.which ("gh"):
      console.err ("GitHub CLI (gh) not installed")
      console.hint ("https://cli.github.com")
      raise typer.Exit (1)

   console.header ("Pull Request")

   b = git.branch ()
   base = git.base_branch ()

   if b == base:
      console.err (f"Cannot create PR from {base}")
      console.hint ("imp branch <description>")
      raise typer.Exit (1)

   log = git.log_oneline (rev_range=f"{base}..{b}")

   if not log:
      console.err (f"No commits on {b}")
      raise typer.Exit (1)

   console.label ("Branch")
   console.item (f"{b} → {base}")
   console.out.print ()

   console.items ("Commits", log)

   d = git.diff_range (f"{base}..{b}", max_lines=ai.MAX_DIFF_LINES)

   pr_content = console.spin (
      "Generating PR...",
      ai.smart,
      prompts.pr (b, log, d),
   )

   title = ""
   description = ""
   for line in pr_content.splitlines ():
      if line.startswith ("TITLE:"):
         title = line [6:].strip ()
         break

   desc_parts = pr_content.split ("DESCRIPTION:", 1)
   if len (desc_parts) > 1:
      description = desc_parts [1].strip ()

   if not title:
      console.warn ("Could not parse title, using branch name")
      title = b

   console.label ("Title")
   console.item (title)
   console.out.print ()

   console.label ("Description")
   console.divider ()
   console.md (description)
   console.divider ()
   console.out.print ()

   choice = console.choose ("Create PR?", [ "Yes", "Edit", "No" ])

   if choice == "Edit":
      edited = console.edit (f"{title}\n\n{description}")
      lines = edited.splitlines ()
      title = lines [0] if lines else title
      description = "\n".join (lines [2:]) if len (lines) > 2 else description
   elif choice == "No":
      console.muted ("Cancelled")
      raise typer.Exit (0)

   if not git.has_upstream ():
      console.spin ("Pushing to origin...", git.push, False, True, b)

   try:
      result = subprocess.run (
         [
            "gh", "pr", "create",
            "--title", title,
            "--body", description,
            "--base", base,
         ],
         capture_output=True,
         text=True,
         check=True,
      )
      pr_url = result.stdout.strip ()
   except subprocess.CalledProcessError:
      console.err ("Failed to create PR")
      raise typer.Exit (1)

   console.out.print ()
   console.success ("Created PR")
   console.item (pr_url)

   console.hint ("gh pr view --web to open in browser")
