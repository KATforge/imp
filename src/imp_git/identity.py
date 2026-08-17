import getpass
import os
import re

from imp_git import config, runtime

_RESOURCE_RE = re.compile (r"^[a-z][a-z0-9-]*(?::[a-z0-9][a-z0-9._-]*)+$")


def slug (value: str) -> str:
   """Normalize one human label into a readable resource segment."""

   normalized = re.sub (r"[^a-z0-9._-]+", "-", value.strip ().lower ()).strip ("-._")
   if not normalized:
      raise ValueError ("Name must contain a letter or number")

   return normalized


def resource (kind: str, *parts: str) -> str:
   """Build and validate one colon-namespaced resource identity."""

   value = ":".join ([ kind, *(slug (part) for part in parts) ])
   if not _RESOURCE_RE.fullmatch (value):
      raise ValueError (f"Invalid {kind} identity: {value}")

   return value


def validate (value: str, kind: str = "") -> str:
   """Validate an externally supplied resource identity."""

   if not _RESOURCE_RE.fullmatch (value):
      raise ValueError (f"Invalid resource identity: {value}")
   if kind and not value.startswith (f"{kind}:"):
      raise ValueError (f"Expected {kind} identity: {value}")

   return value


def actor (override: str = "") -> str:
   """Resolve the calling human, agent session, or CI actor."""

   explicit = override or runtime.options.actor_id
   if explicit:
      return validate (explicit, "actor")

   configured = config.get ("actor:id")
   if configured:
      return validate (configured, "actor")

   codex = os.environ.get ("CODEX_THREAD_ID", "")
   if codex:
      return resource ("actor", "codex", codex)

   claude = os.environ.get ("CLAUDE_SESSION_ID", "")
   if claude:
      return resource ("actor", "claude", claude)

   return resource ("actor", "human", getpass.getuser ())


def key (value: str) -> str:
   """Encode a resource identity for a portable filename."""

   validate (value)
   return value.replace (":", "--")
