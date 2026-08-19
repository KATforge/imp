import os
import re
from pathlib import Path
from typing import Any

from imp_git import config, console, git, identity, plans, runtime, state
from imp_git import fingerprint as fingerprints

PREFIX = "feature/"
ATTIC = "refs/imp/attic"
ATTIC_DAYS = 30

_TICKET_RE = re.compile (r"^([A-Za-z]+-[0-9]+)(?:-|$)")


def ticket_of (branch: str) -> str:
   match = _TICKET_RE.match (branch.removeprefix (PREFIX))
   return match.group (1).upper () if match else ""


def name_of (branch: str) -> str:
   bare = branch.removeprefix (PREFIX)
   return _TICKET_RE.sub ("", bare) or bare


def span_key (name: str) -> str:
   return f"imp.span.{name}.order"


def span_of (name: str) -> list [str]:
   value = git.config_get (span_key (name))
   return value.split () if value else []


def _linked_worktrees () -> dict [str, str]:
   """Map each branch checked out in a linked worktree to that worktree's path.

   The first worktree is the primary checkout; a feature branch checked out
   there is someone's working branch, never a managed feature.
   """

   entries = git.worktrees ()
   return {
      entry ["branch"]: str (Path (entry ["worktree"]).resolve ())
      for entry in entries [1:]
      if entry.get ("branch") and entry.get ("worktree")
   }


def _created_at (branch: str) -> str:
   entries = git.reflog_entries (branch)
   return entries [-1] ["date"] if entries else ""


def _derived (branch: str, path: str, target: str) -> dict [str, Any]:
   name = name_of (branch)
   return {
      "branch": branch,
      "created_at": _created_at (branch),
      "name": name,
      "path": path,
      "span": span_of (name),
      "target": target,
      "ticket": ticket_of (branch),
      "worktree_state": "live" if path else "branch-only",
   }


def all () -> list [dict [str, Any]]:
   """Derive every feature from Git itself: a feature/* branch and its worktree."""

   target = git.base_branch ()
   linked = _linked_worktrees ()
   values = [
      _derived (branch, linked.get (f"refs/heads/{branch}", ""), target)
      for branch in git.branch_names (f"{PREFIX}*")
   ]
   return sorted (values, key=lambda value: str (value ["created_at"]))


def find (value: str) -> dict [str, Any] | None:
   features = all ()
   exact = [ feature for feature in features if feature ["branch"] in (value, f"{PREFIX}{value}") ]
   if exact:
      return exact [0]
   matches = [ feature for feature in features if feature ["name"] == value ]
   if len (matches) > 1:
      raise state.StateError (f"Several features are named {value}; use the branch name")
   return matches [0] if matches else None


def label (feature: dict [str, Any]) -> str:
   return f"{feature ['name']} · {feature ['branch']} · {feature ['worktree_state']}"


def pick (title: str, values: list [dict [str, Any]]) -> dict [str, Any]:
   if not values:
      raise state.StateError ("No open features")
   if len (values) == 1:
      return values [0]
   if runtime.options.json or runtime.options.no_input:
      raise state.StateError ("Pass an explicit feature name")
   labels = [ label (feature) for feature in values ]
   selected = console.choose (title, labels)
   return values [labels.index (selected)]


def resolve (
   value: str = "",
   *,
   live: bool = False,
   title: str = "Select feature",
) -> dict [str, Any]:
   if not value:
      candidates = [ feature for feature in all () if not live or feature ["worktree_state"] == "live" ]
      return pick (title, candidates)
   feature = find (value)
   if not feature:
      raise state.StateError (f"Unknown feature: {value}")
   if live and feature ["worktree_state"] != "live":
      raise state.StateError (f"Feature {feature ['name']} has no worktree")
   return feature


def current () -> dict [str, Any] | None:
   root = str (Path (git.repo_root ()).resolve ())
   return next ((feature for feature in all () if feature ["path"] == root), None)


def _primary_path () -> str:
   entries = git.worktrees ()
   if not entries:
      return git.repo_root ()
   return str (Path (entries [0].get ("worktree", git.repo_root ())).resolve ())


def _managed_root () -> Path:
   configured = config.get ("worktrees")
   base = Path (configured).expanduser () if configured else Path.home () / ".worktrees"
   return base / git.repo_name ()


def worktree_path (name: str) -> Path:
   return (_managed_root () / identity.slug (name)).resolve ()


def branch_for (name: str, ticket: str = "") -> str:
   slug = identity.slug (name)
   return f"{PREFIX}{ticket.upper ()}-{slug}" if ticket else f"{PREFIX}{slug}"


def ticket_convention () -> bool:
   """Return whether existing feature branches already carry ticket prefixes."""

   branches = git.branch_names (f"{PREFIX}*")
   return any (ticket_of (branch) for branch in branches)


def _trunk_base (trunk: str) -> tuple [str, str]:
   """Prefer local trunk when it merely leads the remote, the ordinary state after integrating.

   Basing on the remote there would silently drop every feature already integrated and not
   yet pushed. Anything else, including a genuine divergence, still branches from the remote.
   """

   remote_oid = _remote_oid (trunk)
   local_oid = git.rev_parse (trunk)
   if local_oid and remote_oid and git.is_merged (remote_oid, local_oid):
      return trunk, local_oid

   return f"origin/{trunk}", remote_oid


def _remote_oid (trunk: str) -> str:
   output = git.capture ("ls-remote", "origin", f"refs/heads/{trunk}")
   lines = output.strip ().splitlines ()
   return lines [0].split () [0] if lines else ""


def _descriptor (name: str, *, ticket: str = "", span: list [str] | None = None) -> dict [str, Any]:
   slug = identity.slug (name)
   branch_name = branch_for (name, ticket)
   if find (branch_name) or find (slug):
      raise state.StateError (f"Feature already exists: {name}")
   if git.ref_exists (branch_name):
      raise state.StateError (f"Branch already exists: {branch_name}")
   feature_path = worktree_path (slug)
   if feature_path.exists ():
      raise state.StateError (f"Worktree path already exists: {feature_path}")
   trunk = git.base_branch ()
   if git.remote_exists ():
      base_ref, base_oid = _trunk_base (trunk)
   else:
      if not git.ref_exists (trunk):
         raise state.StateError (f"No remote and no local trunk branch: {trunk}")
      base_ref = trunk
      base_oid = git.rev_parse (trunk)
   if not base_oid:
      raise state.StateError (f"Cannot resolve feature base: {base_ref}")
   return {
      "name": slug,
      "branch": branch_name,
      "path": str (feature_path),
      "base:ref": base_ref,
      "base:oid": base_oid,
      "target": trunk,
      "ticket": ticket.upper (),
      "span": list (span or []),
   }


def plan_start (
   name: str,
   *,
   ticket: str = "",
   span: list [str] | None = None,
) -> dict [str, Any]:
   """Create an immutable feature-start plan without reserving Git state."""

   descriptor = _descriptor (name, ticket=ticket, span=span)
   bound = {
      "base:oid": descriptor ["base:oid"],
      "branch": descriptor ["branch"],
      "path": descriptor ["path"],
   }
   items = [
      { "action": "create_branch", "branch": descriptor ["branch"], "base": descriptor ["base:oid"] },
      { "action": "create_worktree", "path": descriptor ["path"] },
   ]
   warnings = []
   if not ticket and ticket_convention ():
      warnings.append ("Existing feature branches carry ticket prefixes; consider --ticket")
   return plans.build (
      "start",
      str (descriptor ["name"]),
      scope={ "repository": git.repo_name (), "branch": descriptor ["branch"] },
      items=items,
      fingerprint=fingerprints.values (bound),
      payload_schema="imp.start-plan.v2",
      payload=descriptor,
      warnings=warnings,
   )


def _validate_start (plan: dict [str, Any]) -> dict [str, Any]:
   descriptor = dict (plan.get ("payload", {}))
   if plan.get ("payload_schema") != "imp.start-plan.v2":
      raise state.StateError ("Unsupported feature-start plan payload")
   if git.ref_exists (str (descriptor ["branch"])) or Path (str (descriptor ["path"])).exists ():
      raise state.StateError ("Feature-start plan is stale")
   base_ref = str (descriptor ["base:ref"])
   if base_ref.startswith ("origin/"):
      current_oid = _remote_oid (str (descriptor ["target"]))
   else:
      current_oid = git.rev_parse (base_ref)
   bound = {
      "base:oid": current_oid,
      "branch": descriptor ["branch"],
      "path": descriptor ["path"],
   }
   if fingerprints.values (bound) != plan.get ("fingerprint"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Feature-start plan is stale")
   return descriptor


def apply_start (plan: dict [str, Any]) -> dict [str, Any]:
   """Apply one exact feature-start plan and return the derived feature."""

   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   base_ref = str (plan.get ("payload", {}).get ("base:ref", ""))
   if base_ref.startswith ("origin/"):
      target = str (plan ["payload"] ["target"])
      git.fetch (remote="origin", refspec=f"+refs/heads/{target}:refs/remotes/origin/{target}")
   descriptor = _validate_start (plan)
   if base_ref.startswith ("origin/") and git.rev_parse (base_ref) != descriptor ["base:oid"]:
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Remote trunk moved after the feature plan")
   path = str (descriptor ["path"])
   branch = str (descriptor ["branch"])
   try:
      git.worktree_add (path, branch, str (descriptor ["base:oid"]))
      span = list (descriptor.get ("span") or [])
      if span:
         git.config_set (span_key (str (descriptor ["name"])), " ".join (span))
   except Exception:
      discard (branch, path)
      raise
   plans.mark (plan, "applied", applied_at=state.now ())
   return _derived (branch, path, str (descriptor ["target"]))


def discard (branch: str, path: str):
   """Remove one feature's worktree, branch, and span order, leaving no trace."""

   if path and Path (path).exists ():
      _leave (path)
      git.worktree_remove (path, force=True)
   if git.ref_exists (branch):
      git.delete_branch (branch, force=True)
   git.config_unset (span_key (name_of (branch)))


def to_attic (branch: str) -> str:
   """Park one branch tip under an expiring attic ref before it is discarded."""

   oid = git.rev_parse (branch)
   if not oid:
      return ""
   ref = f"{ATTIC}/{name_of (branch)}/{state.stamp ()}"
   git.update_ref_checked (ref, oid, "")
   return ref


def expire_attic (days: int = ATTIC_DAYS) -> list [str]:
   """Drop attic refs older than the retention window and return what was removed."""

   from datetime import datetime, timedelta, timezone

   cutoff = (datetime.now (timezone.utc) - timedelta (days=days)).strftime ("%Y%m%dT%H%M%SZ")
   removed = []
   for ref, oid in git.refs (ATTIC).items ():
      when = ref.rsplit ("/", 1) [-1]
      if when < cutoff:
         git.delete_ref_checked (ref, oid)
         removed.append (ref)
   return removed


def _remove_fingerprint (feature: dict [str, Any]) -> str:
   path = str (feature ["path"])
   return fingerprints.values ({
      "branch": feature ["branch"],
      "branch_oid": git.rev_parse (str (feature ["branch"])),
      "path": path,
      "status": git.capture ("-C", path, "status", "--porcelain=v1") if path else "",
   })


def plan_remove (feature: dict [str, Any]) -> dict [str, Any]:
   """Plan removal of one clean feature worktree and its branch."""

   blockers = []
   if feature ["worktree_state"] == "live":
      dirty = git.capture ("-C", str (feature ["path"]), "status", "--porcelain=v1")
      if dirty:
         blockers.append ("Worktree has uncommitted changes")
   return plans.build (
      "worktree-remove",
      str (feature ["name"]),
      scope={ "branch": feature ["branch"] },
      items=[
         { "action": "attic", "branch": feature ["branch"] },
         { "action": "remove_worktree", "path": feature ["path"] },
         { "action": "delete_branch", "branch": feature ["branch"] },
      ],
      fingerprint=_remove_fingerprint (feature),
      payload_schema="imp.remove-plan.v3",
      payload={ "branch": feature ["branch"], "path": feature ["path"] },
      blockers=blockers,
   )


def apply_remove (plan: dict [str, Any]) -> dict [str, Any]:
   """Apply an exact clean-feature removal plan, parking the tip in the attic."""

   if plan.get ("state") != "ready":
      raise state.StateError (f"Plan is {plan.get ('state')}, not ready")
   if plan.get ("payload_schema") != "imp.remove-plan.v3":
      raise state.StateError ("Unsupported worktree removal plan")
   payload = dict (plan ["payload"])
   feature = find (str (payload ["branch"]))
   if not feature or _remove_fingerprint (feature) != plan.get ("fingerprint"):
      plans.mark (plan, "stale", stale_at=state.now ())
      raise state.StateError ("Worktree removal plan is stale")
   attic_ref = to_attic (str (feature ["branch"]))
   discard (str (feature ["branch"]), str (feature ["path"]))
   plans.mark (plan, "applied", applied_at=state.now ())
   return {
      "attic": attic_ref,
      "branch": feature ["branch"],
      "path": feature ["path"],
   }


def _leave (path: str):
   """Step out of a worktree before removing it, so the caller keeps a live directory."""

   target = Path (path).resolve ()
   try:
      current_path = Path.cwd ().resolve ()
   except OSError:
      current_path = None
   if current_path and (current_path == target or target in current_path.parents):
      os.chdir (_primary_path ())


def complete (feature: dict [str, Any], *, branch_oid: str = ""):
   """Remove one integrated feature's worktree, branch, and span order."""

   import subprocess

   branch = str (feature ["branch"])
   if branch_oid and git.rev_parse (branch) != branch_oid:
      raise state.StateError (f"Feature branch changed: {branch}")
   path = str (feature ["path"])
   if path and Path (path).exists ():
      if not git.clean_at (path):
         raise state.StateError ("Completed feature worktree became dirty")
      _leave (path)
      git.worktree_remove (path, force=True)
   if git.ref_exists (branch):
      try:
         git.delete_branch_checked (branch, branch_oid or git.rev_parse (branch))
      except subprocess.CalledProcessError as error:
         raise state.StateError (f"Integrated branch changed: {branch}") from error
   git.config_unset (span_key (str (feature ["name"])))
