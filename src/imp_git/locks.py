from datetime import datetime, timedelta, timezone

from imp_git import git, identity, state

HOURS = 8
PREFIX = "refs/imp/lock"


def key (branch: str) -> str:
   return f"{PREFIX}/{branch}"


def _expires () -> str:
   value = datetime.now (timezone.utc) + timedelta (hours=HOURS)
   return value.isoformat ().replace ("+00:00", "Z")


def _expired (raw: str) -> bool:
   try:
      return datetime.fromisoformat (raw.replace ("Z", "+00:00")) <= datetime.now (timezone.utc)
   except ValueError:
      return True


def _read (branch: str) -> tuple [str, str]:
   oid = git.rev_parse (key (branch))
   return (oid, git.blob_text (oid)) if oid else ("", "")


def _parse (branch: str, raw: str) -> dict [str, str] | None:
   parts = raw.split ()
   if len (parts) < 3 or _expired (parts [2]):
      return None
   return {
      "branch": branch,
      "name": parts [0],
      "actor": parts [1],
      "expires_at": parts [2],
      "base": parts [3] if len (parts) > 3 else "",
      "ticket": parts [4] if len (parts) > 4 else "",
   }


def holder (branch: str) -> dict [str, str] | None:
   """Return the live lock on one branch, or None when free or expired."""

   _, raw = _read (branch)
   return _parse (branch, raw)


def mine (branch: str) -> bool:
   value = holder (branch)
   return bool (value) and value ["actor"] == identity.actor ()


def foreign (branch: str) -> dict [str, str] | None:
   """Return the live lock when another actor holds it."""

   value = holder (branch)
   return value if value and value ["actor"] != identity.actor () else None


def acquire (branch: str, name: str = "", ticket: str = "") -> dict [str, str]:
   """Take or renew one branch lock for the current actor.

   A lock held by someone else refuses. A fresh lock records the branch's current
   object ID as the session base, so the whole session is one undoable layer; a
   renewal keeps the base, name, and ticket unless new ones are given. The lock is
   a blob under refs/imp/lock, moved by compare-and-swap so racing acquirers get
   exactly one winner. Locks expire on their own after 8 hours.
   """

   previous, raw = _read (branch)
   existing = _parse (branch, raw)
   actor = identity.actor ()
   if existing and existing ["actor"] != actor:
      raise state.StateError (
         f"{branch} is locked by {existing ['actor']} ({existing ['name']}) until {existing ['expires_at']}"
      )
   label = identity.slug (name) if name else (existing ["name"] if existing else identity.slug (branch))
   base = existing ["base"] if existing and existing ["base"] else git.rev_parse (branch)
   mark = (ticket or (existing ["ticket"] if existing else "")).upper ()
   record = {
      "branch": branch, "name": label, "actor": actor,
      "expires_at": _expires (), "base": base, "ticket": mark,
   }
   value = f"{label} {actor} {record ['expires_at']} {base}"
   if mark:
      value += f" {mark}"
   blob = git.hash_blob (value)
   move = f"update {key (branch)} {blob} {previous}" if previous else f"create {key (branch)} {blob}"
   try:
      git.update_refs ([ move ])
   except state.StateError:
      taken = holder (branch)
      if taken and taken ["actor"] != actor:
         raise state.StateError (
            f"{branch} was locked by {taken ['actor']} ({taken ['name']}) during acquisition"
         ) from None
      raise
   return record


def release (branch: str):
   previous, _ = _read (branch)
   if previous:
      git.update_refs ([ f"delete {key (branch)} {previous}" ])


def sweep () -> list [str]:
   """Drop expired, malformed, or legacy lock entries and return what was removed."""

   removed = []
   for ref, oid in git.refs (PREFIX).items ():
      if not _parse (ref.removeprefix (f"{PREFIX}/"), git.blob_text (oid)):
         git.update_refs ([ f"delete {ref} {oid}" ])
         removed.append (ref)
   for entry in git.config_entries (r"^imp\.lock\."):
      git.config_unset (entry)
      removed.append (entry)
   return removed
