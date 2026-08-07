import json
import sys
from typing import Any

from imp_git import runtime


def envelope (
   schema: str,
   command: str,
   data: dict [str, Any],
   *,
   ok: bool = True,
   warnings: list [str] | None = None,
) -> dict [str, Any]:
   """Build one versioned machine result."""

   return {
      "schema": schema,
      "command": command,
      "ok": ok,
      "data": data,
      "warnings": warnings or [],
   }


def emit (
   schema: str,
   command: str,
   data: dict [str, Any],
   *,
   json_output: bool = False,
   ok: bool = True,
   warnings: list [str] | None = None,
) -> dict [str, Any]:
   """Emit a machine result when JSON output is active and always return it."""

   value = envelope (schema, command, data, ok=ok, warnings=warnings)
   if json_output or runtime.options.json:
      sys.stdout.write (json.dumps (value, indent=3, sort_keys=True) + "\n")

   return value
