from typing import Any

from imp_git import state


def build (
   operation: str,
   label: str,
   *,
   items: list [dict [str, Any]],
   payload_schema: str,
   payload: dict [str, Any],
   scope: dict [str, Any] | None = None,
   fingerprint: str = "",
   checks: list [dict [str, Any]] | None = None,
   warnings: list [str] | None = None,
   blockers: list [str] | None = None,
) -> dict [str, Any]:
   """Describe exactly what one command will do, for display and approval.

   A candidate lives only for the invocation that built it. Its durable half is
   already in the object database as a commit, so nothing is written here.
   """

   blocked = blockers or []

   return {
      "schema": "imp.plan.v1",
      "command": f"imp {operation}",
      "label": label,
      "state": "blocked" if blocked else "ready",
      "scope": scope or {},
      "items": items,
      "checks": checks or [],
      "warnings": warnings or [],
      "blockers": blocked,
      "created_at": state.now (),
      "fingerprint": fingerprint,
      "payload_schema": payload_schema,
      "payload": payload,
   }


def mark (plan: dict [str, Any], value: str, **audit: Any) -> dict [str, Any]:
   """Record an outcome on the in-memory candidate."""

   plan ["state"] = value
   plan.update (audit)

   return plan
