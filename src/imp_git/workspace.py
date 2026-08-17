import functools
from pathlib import Path
from typing import Any

import yaml

from imp_git import state

MANIFEST = "workspace.yaml"
LEGACY = "temper.yaml"
SCHEMAS = { "katforge.workspace.v1", "temper.workspace.v1" }


def find (start: Path | None = None) -> Path | None:
   """Locate the nearest workspace manifest at or above one directory."""

   current = (start or Path.cwd ()).resolve ()

   for directory in [ current, *current.parents ]:
      for name in [ MANIFEST, LEGACY ]:
         candidate = directory / name
         if candidate.is_file ():
            return candidate

   return None


def _services (value: dict [str, Any], root: Path) -> dict [str, dict [str, Any]]:
   raw = value.get ("services")
   if not isinstance (raw, dict) or not raw:
      raise state.StateError (f"{MANIFEST} requires a non-empty services map")

   services = {}
   for name, spec in raw.items ():
      if not isinstance (spec, dict):
         raise state.StateError (f"{MANIFEST}: service {name} must be a map")
      needs = spec.get ("needs") or {}
      if isinstance (needs, list):
         needs = dict.fromkeys (needs, "*")
      if not isinstance (needs, dict):
         raise state.StateError (f"{MANIFEST}: service {name} needs must be a map")
      path = str (spec.get ("path", "") or "")
      services [str (name)] = {
         "needs": sorted (str (value) for value in needs),
         "path": str ((root / path).resolve ()) if path else "",
      }

   for name, spec in services.items ():
      missing = sorted (set (spec ["needs"]) - set (services))
      if missing:
         raise state.StateError (f"{MANIFEST}: service {name} needs unknown services: {', '.join (missing)}")

   return services


@functools.cache
def load (start: str = "") -> dict [str, Any] | None:
   """Return the discovered workspace, or None outside one."""

   path = find (Path (start) if start else None)
   if not path:
      return None

   root = path.parent
   value = yaml.safe_load (path.read_text ()) or {}
   include = str (value.pop ("include", "") or "").strip ()

   if include:
      included = (root / include).resolve ()
      if not included.is_relative_to (root.resolve ()):
         raise state.StateError (f"{MANIFEST} include must stay inside the workspace")
      value = { **(yaml.safe_load (included.read_text ()) or {}), **value }

   if value.get ("schema") not in SCHEMAS:
      raise state.StateError (f"Unsupported workspace schema: {value.get ('schema')}")

   return {
      "name": str (value.get ("name") or root.name),
      "root": str (root),
      "services": _services (value, root),
   }


def require (start: str = "") -> dict [str, Any]:
   value = load (start)
   if not value:
      raise state.StateError (f"No {MANIFEST} found at or above the current directory")
   return value


def repositories (value: dict [str, Any]) -> dict [str, str]:
   """Return every service alias that owns a repository on disk."""

   return {
      name: spec ["path"]
      for name, spec in value ["services"].items ()
      if spec ["path"] and Path (spec ["path"]).is_dir ()
   }


def resolve (value: dict [str, Any], alias: str) -> str:
   available = repositories (value)
   if alias not in available:
      known = ", ".join (sorted (available))
      raise state.StateError (f"Unknown workspace repository: {alias} (known: {known})")
   return available [alias]


def order (value: dict [str, Any], selected: list [str]) -> list [str]:
   """Return the selected services in dependency-first order."""

   services = value ["services"]
   unknown = sorted (set (selected) - set (services))
   if unknown:
      raise state.StateError (f"Unknown workspace services: {', '.join (unknown)}")

   ordered: list [str] = []
   visiting: list [str] = []
   visited: set [str] = set ()

   def visit (name: str):
      if name in visited:
         return
      if name in visiting:
         chain = " -> ".join ([ *visiting [visiting.index (name):], name ])
         raise state.StateError (f"{MANIFEST} dependency cycle: {chain}")
      visiting.append (name)
      for dependency in services [name] ["needs"]:
         visit (dependency)
      visiting.pop ()
      visited.add (name)
      ordered.append (name)

   for name in sorted (services):
      visit (name)

   chosen = set (selected)
   return [ name for name in ordered if name in chosen ]


def alias_for (value: dict [str, Any], repository: str) -> str:
   """Return the service alias one repository path belongs to."""

   target = Path (repository).resolve ()
   for name, path in sorted (repositories (value).items ()):
      if Path (path).resolve () == target:
         return name
   raise state.StateError (f"Repository is not a workspace member: {repository}")
