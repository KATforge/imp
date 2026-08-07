import subprocess

import typer

from imp_git import ai, console, gh, git, prompts, validate


def _parse_response (content: str) -> tuple [str, str]:
   title = ""
   for line in content.splitlines ():
      if line.startswith ("TITLE:"):
         title = line [6:].strip ()
         break

   description = ""
   parts = content.split ("DESCRIPTION:", 1)
   if len (parts) > 1:
      description = parts [1].strip ()

   return title, description

def _validate_content (title: str, description: str):
   if not validate.publishable (f"{title}\n{description}"):
      console.fatal ("Pull request text must not include AI attribution or actor IDs")

def pr (
   yes: bool = typer.Option (False, "--yes", "-y", help="Accept AI description without review"),
   whisper: str = typer.Option ("", "--whisper", "-w", help="Hint to guide the AI"),
   into: str = typer.Option ("", "--into", "-i", help="Target branch (defaults to the repo's base branch)"),
   update: bool = typer.Option (False, "--update", "-u", help="Update the existing PR's title and description"),
):
   """Create a GitHub pull request with AI-generated description.

   Diffs the current branch against the base branch (or --into target),
   then uses AI to generate a PR title and description. Pushes to origin
   if needed and creates the PR via the gh CLI. With --update, rewrites
   the title and description of the branch's existing open PR instead
   of creating a new one. Requires gh to be installed.
   """

   git.require ()
   gh.require ()

   b = git.branch ()
   base = into or git.base_branch ()

   if b == base:
      console.hint ("imp branch <description>")
      console.fatal (f"Cannot create PR from {base}")

   if git.remote_exists ():
      console.spin ("Fetching...", git.fetch, False)

   if git.ref_exists (f"origin/{base}"):
      base_ref = f"origin/{base}"
   elif git.ref_exists (base):
      base_ref = base
   else:
      console.hint ("imp pr --into <branch> to pick a target")
      console.fatal (f"Base branch {base} not found")

   log = git.log_oneline (rev_range=f"{base_ref}..{b}")

   if not log:
      console.fatal (f"No commits on {b} that aren't on {base}")

   existing = {}
   if update:
      existing = gh.pr_view (b)

      if existing.get ("state") != "OPEN":
         console.hint ("imp pr to create one")
         console.fatal (f"No open PR found for {b}")

   console.header ("Pull Request")

   console.label ("Branch")
   console.item (f"{b} → {base}")
   console.out.print ()

   console.items ("Commits", log)
   console.out.print ()

   d = ai.truncate (git.diff_range (f"{base_ref}..{b}"))

   pr_content = console.spin (
      "Thinking...",
      ai.smart,
      prompts.pr (b, log, d, whisper),
      False,
   )

   title, description = _parse_response (pr_content)

   if not title:
      console.warn ("Could not parse title, using branch name")
      title = b

   _validate_content (title, description)

   console.label ("Title")
   console.item (title)
   console.out.print ()

   console.label ("Description")
   console.divider ()
   console.md (description)
   console.divider ()
   console.out.print ()

   verb = "Update" if update else "Create"

   if not yes:
      choice = console.choose (f"{verb} PR?", [ "Yes", "Edit", "No" ])

      if choice == "Edit":
         edited = console.edit (f"{title}\n\n{description}")
         lines = edited.splitlines ()
         title = lines [0] if lines else title
         description = "\n".join (lines [2:]) if len (lines) > 2 else description
      elif choice == "No":
         console.muted ("Cancelled")
         raise typer.Exit (0)

   _validate_content (title, description)

   if not git.has_upstream ():
      console.spin ("Pushing to origin...", git.push, False, True, b)

   try:
      if update:
         pr_url = gh.pr_edit (existing ["number"], title, description) or existing ["url"]
      else:
         pr_url = gh.pr_create (title, description, base, b)
   except subprocess.CalledProcessError as e:
      err = (e.stderr or "").strip ()

      if err:
         console.muted (err)

      console.fatal (f"Failed to {verb.lower ()} PR")

   console.out.print ()
   console.success (f"{verb}d PR")
   console.item (pr_url)

   console.hint ("gh pr view --web to open in browser")
