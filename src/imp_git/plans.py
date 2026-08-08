from pathlib import Path
from typing import Any

from imp_git import console, identity, runtime, state

_SCHEMAS = { "imp.plan.v1", "katforge.plan.v1" }


def _directory () -> Path:
   return state.root () / "plans"


def _path (plan_id: str) -> Path:
   return _directory () / f"{identity.key (plan_id)}.json"


def _sequence (operation: str, label: str) -> int:
   prefix = f"plan:{identity.slug (operation)}:{identity.slug (label)}:"
   numbers = []
   for plan in all ():
      plan_id = str (plan.get ("plan_id", ""))
      if not plan_id.startswith (prefix):
         continue
      try:
         numbers.append (int (plan_id.rsplit (":", 1) [1]))
      except ValueError:
         continue

   return max (numbers, default=0) + 1


def create (
   operation: str,
   label: str,
   *,
   scope: dict [str, Any],
   items: list [dict [str, Any]],
   fingerprint: str,
   payload_schema: str,
   payload: dict [str, Any],
   checks: list [dict [str, Any]] | None = None,
   warnings: list [str] | None = None,
   blockers: list [str] | None = None,
   persist: bool = True,
) -> dict [str, Any]:
   """Persist one immutable ready or blocked operation plan."""

   def build () -> dict [str, Any]:
      sequence = _sequence (operation, label)
      plan_id = identity.resource ("plan", operation, label, str (sequence))
      blocked = blockers or []
      plan = {
         "schema": "imp.plan.v1",
         "plan_id": plan_id,
         "command": f"imp {operation}",
         "label": label,
         "state": "blocked" if blocked else "ready",
         "scope": scope,
         "items": items,
         "checks": checks or [],
         "warnings": warnings or [],
         "blockers": blocked,
         "created_at": state.now (),
         "fingerprint": fingerprint,
         "payload_schema": payload_schema,
         "payload": payload,
      }
      if persist:
         state.atomic_write (_path (plan_id), plan)
      return plan

   if not persist:
      return build ()
   with state.lock ("plans"):
      return build ()


def load (plan_id: str) -> dict [str, Any]:
   """Load one plan by its typed identity."""

   identity.validate (plan_id, "plan")
   return _read (_path (plan_id))


def _read (path: Path) -> dict [str, Any]:
   value = state.read (path)
   if value.get ("schema") not in _SCHEMAS:
      raise state.StateError (f"Unsupported Imp plan schema: {value.get ('schema')}")
   return value


def all (operation: str = "") -> list [dict [str, Any]]:
   """List plans, newest first, optionally for one operation."""

   directory = _directory ()
   if not directory.exists ():
      return []

   values = []
   for path in directory.glob ("plan--*.json"):
      try:
         value = _read (path)
      except state.StateError:
         continue
      if operation and value.get ("command") != f"imp {operation}":
         continue
      values.append (value)

   return sorted (values, key=lambda value: str (value.get ("created_at", "")), reverse=True)


def resolve (operation: str, plan_id: str = "") -> dict [str, Any]:
   """Resolve an explicit plan or open the ready-plan picker."""

   if plan_id:
      plan = load (plan_id)
      if plan.get ("command") != f"imp {operation}":
         raise state.StateError (f"Plan belongs to {plan.get ('command')}, not imp {operation}")
      return plan

   ready = [ plan for plan in all (operation) if plan.get ("state") == "ready" ]
   if not ready:
      raise state.StateError (f"No ready imp {operation} plan")
   if runtime.options.json or runtime.options.no_input:
      raise state.StateError (f"Pass an explicit imp {operation} plan ID")
   labels = [ f"{plan ['label']}  ({plan ['created_at']})" for plan in ready ]
   selected = console.choose (f"Select imp {operation} plan", labels)
   return ready [labels.index (selected)]


def mark (plan: dict [str, Any], value: str, **audit: Any) -> dict [str, Any]:
   """Update only mutable plan state and audit fields."""

   lock_name = identity.key (str (plan ["plan_id"]))
   with state.lock (lock_name):
      updated = dict (plan)
      updated ["state"] = value
      updated.update (audit)
      updated ["updated_at"] = state.now ()
      state.atomic_write (_path (str (plan ["plan_id"])), updated)
      return updated
