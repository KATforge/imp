import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from imp_git import identity

CAPABILITIES = { "direct-edit" }
GRANT_MINUTES = 30
REQUEST_MINUTES = 2


class GuardError (RuntimeError):
   """Raised when a guard request or grant is invalid."""


def _now () -> datetime:
   return datetime.now (timezone.utc)


def _stamp (value: datetime) -> str:
   return value.isoformat ().replace ("+00:00", "Z")


def _time (value: str) -> datetime:
   try:
      return datetime.fromisoformat (value.replace ("Z", "+00:00"))
   except ValueError as error:
      raise GuardError (f"Invalid guard expiration: {value}") from error


def _root () -> Path:
   state = Path (os.environ.get ("XDG_STATE_HOME", str (Path.home () / ".local/state")))
   return state / "imp" / "guards"


def _key (repository: str, actor_id: str, capability: str) -> str:
   value = "\0".join ([ str (Path (repository).resolve ()), actor_id, capability ])
   return hashlib.sha256 (value.encode ()).hexdigest ()


def _path (kind: str, repository: str, actor_id: str, capability: str) -> Path:
   return _root () / kind / f"{_key (repository, actor_id, capability)}.json"


def _write (path: Path, value: dict [str, Any]):
   path.parent.mkdir (parents=True, exist_ok=True)
   temporary = path.with_name (f".{path.name}.{os.getpid ()}.tmp")
   try:
      temporary.write_text (json.dumps (value, indent=3, sort_keys=True) + "\n")
      temporary.chmod (0o600)
      temporary.replace (path)
   finally:
      temporary.unlink (missing_ok=True)


def _read (path: Path, schema: str) -> dict [str, Any] | None:
   try:
      value = json.loads (path.read_text ())
   except FileNotFoundError:
      return None
   except (json.JSONDecodeError, OSError) as error:
      raise GuardError (f"Invalid Imp guard state: {path}") from error
   if not isinstance (value, dict) or value.get ("schema") != schema:
      raise GuardError (f"Unsupported Imp guard state: {path}")
   if _time (str (value.get ("expires_at", ""))) > _now ():
      return value
   path.unlink (missing_ok=True)
   return None


def _capability (value: str) -> str:
   if value not in CAPABILITIES:
      raise GuardError (f"Unsupported guard capability: {value}")
   return value


def prepare (
   repository: str,
   actor_id: str,
   capability: str,
   *,
   provider: str,
   session_id: str,
) -> dict [str, Any]:
   """Record that a provider is about to ask a human for one guard grant."""

   capability = _capability (capability)
   actor_id = identity.validate (actor_id, "actor")
   repository = str (Path (repository).resolve ())
   value = {
      "schema": "imp.guard-request.v1",
      "actor_id": actor_id,
      "capability": capability,
      "expires_at": _stamp (_now () + timedelta (minutes=REQUEST_MINUTES)),
      "provider": identity.slug (provider),
      "repository": repository,
      "session_id": session_id,
   }
   _write (_path ("requests", repository, actor_id, capability), value)
   return value


def _requests (repository: str, capability: str) -> list [dict [str, Any]]:
   directory = _root () / "requests"
   if not directory.is_dir ():
      return []
   values = []
   for path in directory.glob ("*.json"):
      value = _read (path, "imp.guard-request.v1")
      if value and value.get ("repository") == repository and value.get ("capability") == capability:
         values.append (value)
   return values


def grant (repository: str, actor_id: str, capability: str) -> dict [str, Any]:
   """Consume one provider-created request and create its temporary grant."""

   capability = _capability (capability)
   repository = str (Path (repository).resolve ())
   actor_id = identity.validate (actor_id, "actor") if actor_id else ""
   request = _read (_path ("requests", repository, actor_id, capability), "imp.guard-request.v1") if actor_id else None
   if not request:
      candidates = _requests (repository, capability)
      if len (candidates) != 1:
         raise GuardError ("No unique provider-approved guard request is waiting")
      request = candidates [0]
      actor_id = str (request ["actor_id"])

   now = _now ()
   value = {
      "schema": "imp.guard-grant.v1",
      "actor_id": actor_id,
      "capability": capability,
      "expires_at": _stamp (now + timedelta (minutes=GRANT_MINUTES)),
      "granted_at": _stamp (now),
      "provider": request ["provider"],
      "repository": repository,
      "session_id": request ["session_id"],
   }
   _write (_path ("grants", repository, actor_id, capability), value)
   _path ("requests", repository, actor_id, capability).unlink (missing_ok=True)
   return value


def active (repository: str, actor_id: str, capability: str) -> dict [str, Any] | None:
   """Return one live grant for an exact repository, actor, and capability."""

   capability = _capability (capability)
   actor_id = identity.validate (actor_id, "actor")
   repository = str (Path (repository).resolve ())
   return _read (_path ("grants", repository, actor_id, capability), "imp.guard-grant.v1")


def list_ (repository: str = "") -> list [dict [str, Any]]:
   """List live grants, optionally limited to one repository."""

   resolved = str (Path (repository).resolve ()) if repository else ""
   directory = _root () / "grants"
   if not directory.is_dir ():
      return []
   values = []
   for path in directory.glob ("*.json"):
      value = _read (path, "imp.guard-grant.v1")
      if value and (not resolved or value.get ("repository") == resolved):
         values.append (value)
   return sorted (values, key=lambda value: (str (value ["repository"]), str (value ["actor_id"])))


def revoke (repository: str = "", actor_id: str = "", capability: str = "") -> int:
   """Remove matching requests and grants and return the number removed."""

   resolved = str (Path (repository).resolve ()) if repository else ""
   if actor_id:
      actor_id = identity.validate (actor_id, "actor")
   if capability:
      _capability (capability)
   removed = 0
   for kind, schema in [ ("grants", "imp.guard-grant.v1"), ("requests", "imp.guard-request.v1") ]:
      directory = _root () / kind
      if not directory.is_dir ():
         continue
      for path in directory.glob ("*.json"):
         value = _read (path, schema)
         if not value:
            continue
         if resolved and value.get ("repository") != resolved:
            continue
         if actor_id and value.get ("actor_id") != actor_id:
            continue
         if capability and value.get ("capability") != capability:
            continue
         path.unlink (missing_ok=True)
         removed += 1
   return removed
