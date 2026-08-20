from typing import Annotated, Any

import typer

from imp_git import ai, approval, console, features, fingerprint, gh, git, plans, state, validate


def _fingerprint (payload: dict [str, Any]) -> str:
   return fingerprint.values ({
      "base": payload ["base"],
      "head": git.branch (),
      "oid": git.rev_parse ("HEAD"),
   })


def _described (head: str, base: str, message: str) -> tuple [str, str]:
   """Compose the title and body: exact when given, AI-written from the diff otherwise."""

   commits = git.capture ("log", "--reverse", "--format=- %s", f"{base}..{head}").strip ()
   if message:
      return message, commits or f"- {message}"
   ticket = features.ticket_of (head)
   value = ai.pull_request (git.capture ("diff", f"{base}...{head}"), commits, ticket)
   title = str (value.get ("title", "")).strip () or git.subject (head) or head
   if ticket and ticket not in title:
      title = f"{ticket} {title}"
   body = str (value.get ("body", "")).strip () or commits
   return title [:70], body


def plan_pr (into: str = "", message: str = "") -> dict [str, Any]:
   if not gh.available () or not git.remote_exists ():
      raise state.StateError ("Pull requests require origin and the GitHub CLI")
   if not git.is_clean ():
      raise state.StateError ("Commit the working tree before opening a pull request")
   head = git.branch ()
   base = into or git.base_branch ()
   if not head or head == base:
      raise state.StateError (f"Cannot open a pull request from {head or 'detached HEAD'}")
   existing = gh.pr_view (head)
   title, body = _described (head, base, message)
   if not validate.publishable (f"{title}\n{body}"):
      raise state.StateError ("Pull request text contains AI attribution or an actor ID")
   payload = {
      "base": base,
      "body": body,
      "head": head,
      "oid": git.rev_parse ("HEAD"),
      "title": title,
      "url": str (existing.get ("url", "")),
   }
   return plans.build (
      "pr", head,
      scope={ "repository": git.repo_name (), "branch": head },
      items=[
         { "action": "push", "branch": head },
         { "action": "update_pr" if existing else "create_pr", "base": base, "head": head },
      ],
      fingerprint=_fingerprint (payload),
      payload_schema="imp.pr-plan.v1",
      payload=payload,
   )


def apply_pr (plan: dict [str, Any]) -> dict [str, Any]:
   if plan.get ("state") != "ready" or plan.get ("payload_schema") != "imp.pr-plan.v1":
      raise state.StateError ("Invalid pull request plan")
   payload = dict (plan ["payload"])
   if not git.is_clean () or _fingerprint (payload) != plan.get ("fingerprint"):
      raise state.StateError ("Pull request plan is stale")
   git.push (set_upstream=True, target=str (payload ["head"]))
   url = str (payload ["url"])
   if url:
      gh.pr_update (
         str (payload ["head"]), str (payload ["base"]),
         str (payload ["title"]), str (payload ["body"]),
      )
   else:
      url = gh.pr_create (
         str (payload ["title"]), str (payload ["body"]),
         str (payload ["base"]), str (payload ["head"]),
      )
   plans.mark (plan, "applied", applied_at=state.now ())
   return { **payload, "url": url }


def _show (plan: dict [str, Any]):
   payload = plan ["payload"]
   console.header ("Pull request")
   console.table ([ "Field", "Value" ], [
      [ "Head", str (payload ["head"]) ],
      [ "Base", str (payload ["base"]) ],
      [ "Title", str (payload ["title"]) ],
      [ "Mode", "update" if payload ["url"] else "create" ],
   ])
   console.raw (str (payload ["body"]))


def pr (
   into: Annotated [str, typer.Option ("--into", help="Target branch; defaults to trunk")] = "",
   message: Annotated [
      str,
      typer.Option ("--message", "-m", help="Exact title to use; nothing is sent to AI"),
   ] = "",
):
   """Push the current branch and open or update its GitHub pull request.

   The description is written by AI from the branch's diff against the base: a title
   under 70 characters carrying the ticket, and at most five one-line bullets covering
   only what a reviewer must know. The exact text is shown for approval before
   anything is pushed. With -m the given title is used, the body is the commit list,
   and nothing is sent to AI.

   Idempotent per branch: an existing pull request is updated, never duplicated.
   Refuses text containing AI attribution or actor IDs. Requires origin and the
   GitHub CLI; always confirms, since it writes to a remote.
   """

   git.require ()
   try:
      plan = plan_pr (into, message)
   except state.StateError as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      noun="pull request",
      confirm="Push and open this pull request?",
      result_schema="imp.pr.v1",
      apply=apply_pr,
      show=_show,
      success=lambda data: console.success (f"Pull request ready: {data ['url']}"),
      destructive=True,
   )
