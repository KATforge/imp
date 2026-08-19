from typing import Annotated

import typer

from imp_git import approval, commit_plan, console, git, state


def _show (plan: dict):
   console.header ("Commit plan")
   payload = plan ["payload"]
   console.table ([ "Commit", "Files" ], [[ str (payload ["message"]), str (len (payload ["paths"])) ]])
   for warning in plan.get ("warnings", []):
      console.warn (str (warning))
   for blocker in plan.get ("blockers", []):
      console.err (str (blocker))


def commit (
   message: Annotated [
      str,
      typer.Option (
         "--message", "-m",
         help="Exact Conventional Commits subject to use; nothing is sent to AI",
      ),
   ] = "",
):
   """Create one exact local commit from staged changes, or every dirty path when nothing is staged.

   The commit is built off-ref from an isolated index and the branch only moves when it
   succeeds, so a failure leaves the repository untouched. Anything staged but not
   selected stays staged.

   Without -m the selected diff is sent to AI for a Conventional Commits subject; that
   is the only content this command sends anywhere. With -m the given subject is used
   verbatim and nothing leaves the machine. Never pushes.
   """

   git.require ()
   try:
      plan = commit_plan.create (message=message)
   except (state.StateError, ValueError) as error:
      console.fatal (str (error))

   def success (data: dict):
      for value in data ["commits"]:
         console.success (str (value ["message"]))

   return approval.run (
      plan,
      noun="commit",
      confirm="Create this local commit?",
      result_schema="imp.commit.v1",
      apply=commit_plan.apply,
      show=_show,
      success=success,
   )
