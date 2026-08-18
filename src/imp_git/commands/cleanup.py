from imp_git import (
   approval,
   console,
   identity,
   result,
   runtime,
)
from imp_git import (
   cleanup as cleanup_mod,
)


def _target (item: dict) -> str:
   label = str (item.get ("name") or item.get ("label") or item.get ("path") or "state")
   branch = str (item.get ("branch", ""))

   return f"{label} ({branch})" if branch else label


def _show (plan: dict):
   console.header ("Cleanup")
   if plan ["items"]:
      console.table (
         [ "Action", "Target" ],
         [
            [ str (item ["action"]), _target (item) ]
            for item in plan ["items"]
         ],
      )
   else:
      console.muted ("No safe cleanup actions")
   remaining = plan ["payload"] ["remaining"]
   if remaining:
      console.out.print ()
      console.label ("Preserved")
      console.table (
         [ "Kind", "Name", "Reason", "Next" ],
         [ [ item ["kind"], item ["name"], item ["reason"], item ["next"] ] for item in remaining ],
      )


def _success (data: dict):
   count = len (data ["applied"])
   if data ["clean"]:
      console.success (f"Clean ({count} reconciled)")
      return
   console.warn (f"Reconciled {count}; preserved {len (data ['remaining'])} item(s)")


def cleanup ():
   """Reconcile safe repository residue and preserve unique work."""

   plan = cleanup_mod.plan_cleanup ()
   if not plan ["items"] and not runtime.options.dry_run:
      data = {
         "applied": [],
         "clean": not plan ["payload"] ["remaining"],
         "remaining": plan ["payload"] ["remaining"],
      }
      if runtime.options.json:
         result.emit ("imp.cleanup.v1", "imp cleanup", data, json_output=True)
      else:
         _show (plan)
         _success (data)
      return data

   return approval.run (
      plan,
      command="imp cleanup",
      noun="cleanup",
      confirm="Apply these safe cleanup actions?",
      plan_schema="imp.cleanup-plan.v1",
      result_schema="imp.cleanup.v1",
      apply=lambda value: cleanup_mod.apply_cleanup (value, identity.actor (runtime.options.actor_id)),
      show=_show,
      success=_success,
      dry_run=runtime.options.dry_run,
      yes=runtime.options.yes,
      json_output=runtime.options.json,
   )
