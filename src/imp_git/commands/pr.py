import contextlib

import typer

from imp_git import console, gh, git, result, runtime, state, summary, validate


def pr ():
   """Push the current branch and open or update its pull request."""

   git.require ()
   if not gh.available ():
      console.fatal ("The GitHub CLI is required to open a pull request")
   if not git.remote_exists ():
      console.fatal ("A remote is required to open a pull request")

   head = git.branch ()
   base = git.base_branch ()
   if head == base:
      console.fatal (f"Cannot open a pull request from {head} into itself")
   if not git.is_clean ():
      console.fatal ("Commit the working tree before opening a pull request")

   with contextlib.suppress (state.StateError):
      git.fetch (remote="origin", refspec=f"+refs/heads/{base}:refs/remotes/origin/{base}")

   subject = summary.bullet (git.subject (head) or head, summary.cap ())
   body = summary.body (f"origin/{base}" if git.rev_parse (f"origin/{base}") else base, head)
   if not validate.publishable (f"{subject}\n{body}"):
      console.fatal ("Pull request text contains AI attribution or an actor ID")

   existing = gh.pr_view (head)
   console.header ("Open pull request")
   console.table (
      [ "Field", "Value" ],
      [
         [ "Head", head ],
         [ "Base", base ],
         [ "Title", subject ],
         [ "Mode", "update" if existing else "create" ],
      ],
   )
   if runtime.options.no_input and not runtime.options.yes:
      console.fatal ("Non-interactive pull request requires --yes")
   if not runtime.options.yes and not console.confirm (f"Push {head} and open this pull request?"):
      raise typer.Exit (0)

   git.push (set_upstream=True, target=head)
   url = gh.pr_edit (int (existing ["number"]), subject, body) if existing else gh.pr_create (
      subject, body, base, head,
   )
   data = { "base": base, "head": head, "title": subject, "updated": bool (existing), "url": url }
   if runtime.options.json:
      return result.emit ("imp.pr.v1", "imp pr", data, json_output=True)
   console.success (f"Pull request ready: {url}")

   return data
