import contextlib
import re
from typing import Annotated

import typer

from imp_git import console, gh, git, repo, result, runtime, state, validate

_SENTENCE = re.compile (r"(?<=[.!?])\s")


def _cap () -> int:
   value = repo.get ("commit:max_subject", 72)

   return int (value) if str (value).isdigit () else 72


def _bullet (text: str, cap: int) -> str:
   """Reduce one commit subject to a single short line.

   A pull request body is scanned, not read, so each line keeps its first clause
   only and stops at the subject cap on a word boundary rather than mid-word.
   """

   first = _SENTENCE.split (" ".join (text.split ()), 1) [0].rstrip (".!? ")
   if len (first) <= cap:
      return first
   clipped = first [:cap].rsplit (" ", 1) [0]

   return f"{clipped or first [:cap]}…"


def _body (base: str, head: str) -> str:
   """Build a body of one-line bullets, newest work last and duplicates dropped."""

   cap = _cap ()
   lines = list (reversed (git.log_oneline (rev_range=f"{base}..{head}").splitlines ()))
   bullets: list [str] = []
   for line in lines:
      bullet = _bullet (line.split (" ", 1) [-1], cap)
      if bullet and bullet not in bullets:
         bullets.append (bullet)
   if not bullets:
      bullets = [ _bullet (git.subject (head) or head, cap) ]

   return "\n".join (f"- {value}" for value in bullets) + "\n"


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

   subject = _bullet (title or git.subject (head) or head, _cap ())
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
