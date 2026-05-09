"""Cross-repo dependency graph from GitHub Actions workflow refs.

Used by `imp fleet` to ship deps before dependents. When a workflow file
in repo A says `uses: org/B/...@ref`, repo B must ship before A so the ref
resolves to the new content on the next workflow run.

Only GitHub Actions `uses:` is parsed today. Other cross-repo signals
(image refs in k8s manifests, package.json deps, sibling JSON in workflow
inputs) can be added later if a use case demands them.
"""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path

from imp import console

# uses: <owner>/<repo>(/<path>)?@<ref>
#
# Matches both action refs (`actions/checkout@v4`) and reusable workflow refs
# (`katforge/hearth/.github/workflows/release-template.yml@master`). Filtering
# to the local fleet happens at topo-sort time, not at parse time.
_USES_RE = re.compile (
   r'^\s*-?\s*uses:\s*([\w.-]+)/([\w.-]+)(?:/[^@\s]+)?@\S+',
   re.MULTILINE,
)


def origin_slug (repo: Path) -> tuple [str, str] | None:
   """Return (owner, name) parsed from the origin remote URL, lowercased.

   Returns None when origin is missing, points at a non-GitHub-shaped URL,
   or git fails to read it. Lowercase normalization matches GitHub's
   case-insensitive URL routing so callers can compare slugs safely.
   """

   try:
      result = subprocess.run (
         [ "git", "remote", "get-url", "origin" ],
         cwd=repo, capture_output=True, text=True, timeout=10,
      )
   except (subprocess.TimeoutExpired, OSError):
      return None

   if result.returncode != 0:
      return None

   url = result.stdout.strip ().rstrip ("/").removesuffix (".git")

   if url.startswith ("git@") and ":" in url:
      slug = url.split (":", 1) [1]
   elif "://" in url:
      after_scheme = url.split ("://", 1) [1]
      if "/" not in after_scheme:
         return None
      slug = after_scheme.split ("/", 1) [1]
   else:
      return None

   parts = slug.split ("/")
   if len (parts) < 2 or not parts [0] or not parts [1]:
      return None
   return parts [0].lower (), parts [1].lower ()


def workflow_uses (repo: Path) -> set [tuple [str, str]]:
   """Return all (owner, name) referenced via 'uses:' under .github/workflows."""

   wf_dir = repo / ".github" / "workflows"
   if not wf_dir.is_dir ():
      return set ()

   refs: set [tuple [str, str]] = set ()
   for wf in [ *wf_dir.glob ("*.yml"), *wf_dir.glob ("*.yaml") ]:
      try:
         text = wf.read_text ()
      except OSError:
         continue
      for owner, name in _USES_RE.findall (text):
         refs.add ((owner.lower (), name.lower ()))
   return refs


def topo_sort (repos: list [Path]) -> list [Path]:
   """Order repos so cross-repo deps ship before dependents.

   Builds a directed graph from GitHub Actions `uses:` refs that resolve
   within the input set, then runs Kahn's algorithm. Refs to repos outside
   the input (e.g. `actions/checkout`) don't induce ordering. Input order
   is preserved among nodes with equal priority. Cycles fall back to input
   order for the leftover nodes with a console warning.
   """

   if len (repos) < 2:
      return list (repos)

   slug_to_repo: dict [tuple [str, str], Path] = {}
   for r in repos:
      slug = origin_slug (r)
      if slug:
         slug_to_repo [slug] = r

   dependents: dict [Path, list [Path]] = defaultdict (list)
   in_degree: dict [Path, int] = { r: 0 for r in repos }

   for r in repos:
      for ref in workflow_uses (r):
         dep = slug_to_repo.get (ref)
         if dep and dep != r:
            dependents [dep].append (r)
            in_degree [r] += 1

   ordered: list [Path] = []
   ready: deque [Path] = deque (r for r in repos if in_degree [r] == 0)

   while ready:
      r = ready.popleft ()
      ordered.append (r)
      for d in dependents [r]:
         in_degree [d] -= 1
         if in_degree [d] == 0:
            ready.append (d)

   if len (ordered) < len (repos):
      remaining = [ r for r in repos if r not in ordered ]
      console.muted (f"  warning: dep cycle detected; appending {len (remaining)} repo(s) in input order")
      ordered.extend (remaining)

   return ordered
