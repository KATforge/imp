from typing import Annotated, Any

import typer

from imp_git import approval, console, fingerprint, gh, git, plans, runtime, state, validate


def _fingerprint (payload: dict [str, Any]) -> str:
   return fingerprint.values ({
      "base": payload ["base"],
      "head": git.branch (),
      "oid": git.rev_parse ("HEAD"),
   })


def plan_pr (into: str = "") -> dict [str, Any]:
   if not gh.available () or not git.remote_exists ():
      raise state.StateError ("Pull requests require origin and the GitHub CLI")
   if not git.is_clean ():
      raise state.StateError ("Commit the working tree before opening a pull request")
   head = git.branch ()
   base = into or git.base_branch ()
   if not head or head == base:
      raise state.StateError (f"Cannot open a pull request from {head or 'detached HEAD'}")
   existing = gh.pr_view (head)
   title = git.subject (head) or head
   body = git.capture ("log", "--reverse", "--format=- %s", f"{base}..{head}").strip () or f"- {title}"
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


def pr (
   into: Annotated [str, typer.Option ("--into", help="Target branch")] = "",
):
   """Push the current branch and open or update its pull request."""

   git.require ()
   try:
      plan = plan_pr (into)
   except state.StateError as error:
      console.fatal (str (error))
   return approval.run (
      plan,
      command="imp pr",
      noun="pull request",
      confirm="Push and open this pull request?",
      plan_schema="imp.pr-plan.v1",
      result_schema="imp.pr.v1",
      apply=apply_pr,
      show=_show,
      success=lambda data: console.success (f"Pull request ready: {data ['url']}"),
      dry_run=runtime.options.dry_run,
      yes=runtime.options.yes,
      json_output=runtime.options.json,
   )
