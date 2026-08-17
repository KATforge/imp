import contextlib
from typing import Annotated

import typer

from imp_git import console, gh, git, result, runtime, state, validate

_BODY = """## Summary

{summary}

## Commits

{commits}
"""


def _body (base: str, head: str) -> str:
   commits = git.log_oneline (rev_range=f"{base}..{head}") or "(none)"
   subjects = [ line.split (" ", 1) [-1] for line in commits.splitlines () ]
   summary = subjects [0] if len (subjects) == 1 else f"{len (subjects)} commits from `{head}`."

   return _BODY.format (summary=summary, commits="\n".join (f"- {value}" for value in subjects))


def pr (
   into: Annotated [str, typer.Option ("--into", help="Target branch for the pull request")] = "",
   title: Annotated [str, typer.Option ("--title", help="Explicit pull request title")] = "",
):
   """Push the current branch and open or update its pull request."""

   git.require ()
   if not gh.available ():
      console.fatal ("The GitHub CLI is required to open a pull request")
   if not git.remote_exists ():
      console.fatal ("A remote is required to open a pull request")

   head = git.branch ()
   base = into or git.base_branch ()
   if head == base:
      console.fatal (f"Cannot open a pull request from {head} into itself")
   if not git.is_clean ():
      console.fatal ("Commit the working tree before opening a pull request")

   with contextlib.suppress (state.StateError):
      git.fetch (remote="origin", refspec=f"+refs/heads/{base}:refs/remotes/origin/{base}")

   subject = title or git.subject (head) or head
   body = _body (f"origin/{base}" if git.rev_parse (f"origin/{base}") else base, head)
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
