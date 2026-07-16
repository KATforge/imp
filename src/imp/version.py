import re
from pathlib import Path

from imp.validate import COMMIT_RE

def _capitalize (text: str) -> str:
   return text [0].upper () + text [1:] if len (text) > 1 else text

def bump (current: str, level: str) -> str:
   match = re.match (r"^(\d+)\.(\d+)\.(\d+)$", current)
   if not match:
      return level

   parts = list (map (int, match.groups ()))
   idx = {"major": 0, "minor": 1, "patch": 2}.get (level)
   if idx is None:
      return level

   parts [idx] += 1
   for i in range (idx + 1, 3):
      parts [i] = 0

   return ".".join (map (str, parts))

def next_rc (ver: str, existing: list [str]) -> str:
   if not existing:
      return f"{ver}-rc.1"

   highest = 0
   for t in existing:
      match = re.search (r"-rc\.(\d+)$", t)
      if match:
         highest = max (highest, int (match.group (1)))

   return f"{ver}-rc.{highest + 1}"

def changelog_from_commits (subjects: str) -> str:
   added = []
   fixed = []
   changed = []

   for line in subjects.splitlines ():
      line = line.strip ()
      if not line:
         continue

      if re.match (r"^[0-9a-f]+ ", line):
         line = line.split (" ", 1) [1]

      match = COMMIT_RE.match (line)
      if match:
         kind = match.group (1)
         desc = match.group (3)
      else:
         desc = _capitalize (line)
         changed.append (f"- {desc}")
         continue

      desc = _capitalize (desc)

      if kind == "feat":
         added.append (f"- {desc}")
      elif kind == "fix":
         fixed.append (f"- {desc}")
      else:
         changed.append (f"- {desc}")

   sections = []
   if added:
      sections.append ("### Added\n" + "\n".join (added))
   if changed:
      sections.append ("### Changed\n" + "\n".join (changed))
   if fixed:
      sections.append ("### Fixed\n" + "\n".join (fixed))

   return "\n\n".join (sections)

_PKG_VERSION = re.compile (r'("version"\s*:\s*")([^"]*)(")')
_PYPROJECT_VERSION = re.compile (r'^(version\s*=\s*")([^"]*)(")', re.MULTILINE)

# Manifests that carry a copy of the release version, relative to the repo
# root. The git tag is canonical; these are downstream copies kept in
# lockstep on every release. cli/pyproject.toml covers repos whose Python
# package lives one level down (hearth).
MANIFESTS = ( "package.json", "composer.json", "pyproject.toml", "cli/pyproject.toml" )

def manifest_paths (root: Path) -> list [Path]:
   return [ root / rel for rel in MANIFESTS ]

def _pattern_for (path: Path) -> re.Pattern:
   return _PYPROJECT_VERSION if path.suffix == ".toml" else _PKG_VERSION

def read_manifest_version (path: Path) -> str | None:
   """The version a manifest currently declares, or None when the file or
   field is absent (dynamic pyproject versions read as absent — hatch-vcs
   already derives those from the tag)."""
   if not path.is_file ():
      return None

   match = _pattern_for (path).search (path.read_text ())
   return match.group (2) if match else None

def _write_version (path: Path, new_version: str) -> bool:
   if not path.is_file ():
      return False

   text = path.read_text ()
   new_text, n = _pattern_for (path).subn (rf"\g<1>{new_version}\g<3>", text, count=1)

   if n == 0 or new_text == text:
      return False

   path.write_text (new_text)
   return True

def write_package_version (path: Path, new_version: str) -> bool:
   """Rewrite the top-level "version" in a package.json in place, leaving the
   rest of the file (indentation, key order, trailing newline) untouched.

   imp derives the release version from git tags, but `bun publish` reads it
   from package.json — so without this the two drift and every publish 409s on
   the stale version. Targets the FIRST "version": match (always the top-level
   field, above dependencies) like `npm version` does. No-op (False) when
   there's no package.json or no version field — keeps imp git-generic."""
   return _write_version (path, new_version)

def write_pyproject_version (path: Path, new_version: str) -> bool:
   """Rewrite the static `version = "..."` in a pyproject.toml in place.
   Repos with `dynamic = ["version"]` have no such line, so they no-op —
   their build backend already reads the tag."""
   return _write_version (path, new_version)

def sync_manifests (root: Path, new_version: str) -> list [Path]:
   """Write the release version into every manifest the repo carries.
   Returns the paths that changed. Manifests without a version field are
   left alone — keeps imp git-generic."""
   return [ p for p in manifest_paths (root) if _write_version (p, new_version) ]

def write_changelog (path: Path, entry: str):
   if path.is_file ():
      content = path.read_text ()

      lines = content.splitlines (keepends=True)
      insert_at = None
      for i, line in enumerate (lines):
         if line.lstrip ().startswith ("## "):
            insert_at = i
            break

      if insert_at is not None:
         before = "".join (lines [:insert_at])
         after = "".join (lines [insert_at:])
         content = before + entry + "\n\n" + after
      else:
         content = content + "\n" + entry + "\n"

      path.write_text (content)
   else:
      path.write_text (
         f"# Changelog\n\n"
         f"All notable changes to this project will be documented in this file.\n\n"
         f"{entry}\n"
      )
