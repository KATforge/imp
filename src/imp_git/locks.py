from datetime import datetime, timedelta, timezone

from imp_git import git, identity, state

HOURS = 8


def key (branch: str) -> str:
   return f"imp.lock.{branch}.holder"


def _expires () -> str:
   value = datetime.now (timezone.utc) + timedelta (hours=HOURS)
   return value.isoformat ().replace ("+00:00", "Z")


def _expired (raw: str) -> bool:
   try:
      return datetime.fromisoformat (raw.replace ("Z", "+00:00")) <= datetime.now (timezone.utc)
   except ValueError:
      return True


def holder (branch: str) -> dict [str, str] | None:
   """Return the live lock on one branch, or None when free or expired."""

   parts = git.config_get (key (branch)).split ()
   if len (parts) != 3 or _expired (parts [2]):
      return None
   return { "branch": branch, "name": parts [0], "actor": parts [1], "expires_at": parts [2] }


def mine (branch: str) -> bool:
   value = holder (branch)
   return bool (value) and value ["actor"] == identity.actor ()


def foreign (branch: str) -> dict [str, str] | None:
   """Return the live lock when another actor holds it."""

   value = holder (branch)
   return value if value and value ["actor"] != identity.actor () else None


def acquire (branch: str, name: str = "") -> dict [str, str]:
   """Take or renew one branch lock for the current actor.

   A lock held by someone else refuses; a lock of my own renews, keeping its
   name unless a new one is given. Locks expire on their own after 8 hours.
   """

   existing = holder (branch)
   actor = identity.actor ()
   if existing and existing ["actor"] != actor:
      raise state.StateError (
         f"{branch} is locked by {existing ['actor']} ({existing ['name']}) until {existing ['expires_at']}"
      )
   label = identity.slug (name) if name else (existing ["name"] if existing else identity.slug (branch))
   record = { "branch": branch, "name": label, "actor": actor, "expires_at": _expires () }
   git.config_set (key (branch), f"{label} {actor} {record ['expires_at']}")
   return record


def release (branch: str):
   git.config_unset (key (branch))


def sweep () -> list [str]:
   """Drop expired or malformed lock entries and return the keys removed."""

   removed = []
   for entry, value in git.config_entries (r"^imp\.lock\.").items ():
      parts = value.split ()
      if len (parts) != 3 or _expired (parts [2]):
         git.config_unset (entry)
         removed.append (entry)
   return removed
