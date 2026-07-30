import re
from pathlib import Path

from imp import ai, git, prompts
from imp.validate import COMMIT_RE, TYPES_PATTERN

# The Keep-a-Changelog preamble, defined once. Every path that writes a fresh
# CHANGELOG.md reuses it so the header never drifts between generators.
HEADER = (
   "# Changelog\n\n"
   "All notable changes to this project will be documented in this file.\n"
)

MAX_DIFF_LINES = 3000

# Every bullet, AI-written or derived from a subject, is squeezed through
# `normalize_line` before it reaches the file. A changelog is scanned, not read:
# uniform one-liners beat accurate paragraphs, and the diff holds the detail.
_TYPE_PREFIX = re.compile (
   rf"^(?:(?:{TYPES_PATTERN})(\(.+?\))?!?"
   r"|added|changed|deprecated|removed|fixed|security)"
   r":\s*",
   re.I,
)
_PAREN       = re.compile (r"\s*\([^()]*\)")
_SENTENCE    = re.compile (r"(?<=[a-z0-9])\.\s+\S")
_TAIL        = re.compile (
   r"\s+(?:[-–—]\s|so\s|in order to\b|instead of\b|rather than\b"
   r"|which\b|allowing\b|ensuring\b|enabling\b)"
   r"|,\s+(?:so|which|because|allowing|ensuring|enabling)\b",
   re.I,
)

def _capitalize (text: str) -> str:
   return text [0].upper () + text [1:] if len (text) > 1 else text

def normalize_line (text: str) -> str:
   """One changelog bullet, normalized to the house shape: no commit-type
   prefix, no parenthetical aside, no explanatory tail, one sentence, no
   trailing punctuation, capitalized. Returns "" when nothing survives."""
   text = _TYPE_PREFIX.sub ("", re.sub (r"\s+", " ", text.strip ().lstrip ("-*").strip ()))
   text = _PAREN.sub ("", text)

   # A mid-line colon introduces explanation once a clause stands before it.
   head, sep, _ = text.partition (": ")
   if sep and len (head.split ()) >= 3:
      text = head

   sentence = _SENTENCE.search (text)
   if sentence:
      text = text [:sentence.start () + 1]

   tail = _TAIL.search (text)
   if tail:
      text = text [:tail.start ()]

   words = text.rstrip (" .,;:").split ()

   # Over the cap with a comma in reach: the head of the list says it.
   # Nothing else is truncated — a long readable line beats a fragment.
   if len (words) > prompts.MAX_WORDS:
      head = " ".join (words).split (",") [0].split ()
      if len (head) >= 3:
         words = head

   text = " ".join (words).rstrip (" .,;:")

   return _capitalize (text) if text else ""

def normalize (entry: str) -> str:
   """Run every bullet of a generated entry through `normalize_line`, keeping the
   headings that still have bullets under them. Stray prose, bullets that
   squeeze down to nothing, and duplicates the squeeze creates are dropped."""
   sections: list [tuple [str | None, list [str]]] = []
   seen: set [str] = set ()

   for raw in entry.splitlines ():
      stripped = raw.strip ()

      if stripped.startswith ("#"):
         sections.append ((stripped, []))
         continue

      if not stripped.startswith (("-", "*")):
         continue

      text = normalize_line (stripped)
      if not text or text.lower () in seen:
         continue

      seen.add (text.lower ())

      if not sections:
         sections.append ((None, []))

      sections [-1] [1].append (f"- {text}")

   blocks = [
      "\n".join (([ head ] if head else []) + bullets)
      for head, bullets in sections
      if bullets
   ]

   return "\n\n".join (blocks)

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

def base_tuple (ref: str) -> tuple [int, int, int] | None:
   """The (major, minor, patch) of a version or v-tag, ignoring any -rc
   suffix. `base_tuple("v2.3.3-rc.1")` → (2, 3, 3). None if unparseable —
   so non-semver tags are never mistaken for a version to compare."""
   match = re.match (r"^v?(\d+)\.(\d+)\.(\d+)", ref)
   if not match:
      return None
   return tuple (int (x) for x in match.groups ())

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
   seen = set ()

   for line in subjects.splitlines ():
      line = line.strip ()
      if not line:
         continue

      if re.match (r"^[0-9a-f]+ ", line):
         line = line.split (" ", 1) [1]

      match = COMMIT_RE.match (line)
      kind = match.group (1) if match else ""
      desc = normalize_line (match.group (3) if match else line)

      if not desc or desc.lower () in seen:
         continue

      seen.add (desc.lower ())

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

def _filter (commits: list [dict]) -> list [dict]:
   """Drop the commit types listed in `.imp` changelog:skip (chore/release/merge
   by default) so noise never reaches an entry."""
   from imp import repo

   skip = { s.lower () for s in repo.changelog_skip () }
   if not skip:
      return commits

   kept = []
   for c in commits:
      subject = c.get ("subject", "")
      kind = subject.split (":", 1) [0].split ("(", 1) [0].strip ().lower ()

      if kind in skip:
         continue
      if "merge" in skip and subject.lower ().startswith ("merge "):
         continue

      kept.append (c)

   return kept

def collect_diffs (commits: list [dict], max_lines: int = MAX_DIFF_LINES) -> str:
   parts = []
   total = 0

   for c in commits:
      patch = git.show_patch (c ["hash"])
      if not patch:
         continue

      lines = patch.splitlines ()
      if total + len (lines) > max_lines:
         remaining = max_lines - total
         if remaining > 0:
            parts.append ("\n".join (lines [:remaining]))
         break

      parts.append (patch)
      total += len (lines)

   return "\n".join (parts)

def entry (commits: list [dict], fast: bool = False) -> str:
   """The single changelog-entry generator. Reads the actual diffs and asks the
   AI to describe them (a real "what changed"); falls back to the deterministic
   subject-based entry when fast, offline, or diffless. Honors changelog:skip."""
   commits = _filter (commits)
   if not commits:
      return ""

   subjects = "\n".join (c.get ("subject", "") for c in commits)

   if fast:
      return changelog_from_commits (subjects)

   diffs = collect_diffs (commits)
   if not diffs:
      return changelog_from_commits (subjects)

   result = ai.smart (prompts.changelog_entry (diffs))
   text = normalize (ai.strip_fences (result).strip ())

   return text or changelog_from_commits (subjects)

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

_CL_SECTION_RE = re.compile (r"^##\s+\[?(\d+\.\d+\.\d+)")
_CL_SUB_ORDER  = [ "Added", "Changed", "Deprecated", "Removed", "Fixed", "Security" ]

def _split_sections (text: str) -> tuple [str, list [tuple [str | None, str]]]:
   """(preamble, [(version, block), ...]) split at each '## ' header. version
   is None for non-semver headers (e.g. Unreleased) so they're never merged."""
   lines = text.splitlines (keepends=True)
   heads = [ i for i, l in enumerate (lines) if l.lstrip ().startswith ("## ") ]

   if not heads:
      return text, []

   preamble = "".join (lines [:heads [0]])
   sections = []

   for j, start in enumerate (heads):
      end   = heads [j + 1] if j + 1 < len (heads) else len (lines)
      block = "".join (lines [start:end])
      match = _CL_SECTION_RE.match (lines [start].strip ())
      sections.append ((match.group (1) if match else None, block))

   return preamble, sections

def _merge_bodies (blocks: list [str]) -> str:
   """Merge the bodies of several changelog sections: bullets grouped under
   their '### ' subsection in canonical order, identical lines deduped.
   Handles plain-bullet sections (no subsections) too."""
   groups: dict [str, list [str]] = {}
   extra_order: list [str] = []
   flat: list [str] = []
   seen: set [str] = set ()

   def add (bucket: list [str], line: str):
      key = line.strip ()
      if key and key not in seen:
         seen.add (key)
         bucket.append (line.rstrip ())

   for block in blocks:
      current = None
      for line in block.splitlines () [1:]:  # skip the '## ' header line
         stripped = line.strip ()
         if stripped.startswith ("### "):
            current = stripped [4:].strip ()
            if current not in groups:
               groups [current] = []
               extra_order.append (current)
            continue
         if not stripped:
            continue
         add (flat if current is None else groups [current], line)

   out = list (flat)
   if flat and groups:
      out.append ("")

   emitted: set [str] = set ()
   for name in _CL_SUB_ORDER + extra_order:
      if name in groups and name not in emitted:
         emitted.add (name)
         out.append (f"### {name}")
         out.extend (groups [name])
         out.append ("")

   return "\n".join (out).rstrip () + "\n"

def consolidate_changelog (
   text: str,
   floor: tuple [int, int, int],
   new_version: str,
   today: str,
) -> str:
   """Fold every changelog section above `floor` into a single
   [new_version] section dated `today`, keeping sections at or below the
   floor untouched. Returns the text unchanged when nothing sits above the
   floor, so it's safe to call unconditionally."""
   preamble, sections = _split_sections (text)

   collapse = [ b for v, b in sections if v and base_tuple (v) > floor ]
   keep     = [ b for v, b in sections if not (v and base_tuple (v) > floor) ]

   if not collapse:
      return text

   new_section = f"## [{new_version}] - {today}\n\n{_merge_bodies (collapse)}"

   parts = [ preamble.rstrip ("\n"), new_section.rstrip ("\n") ]
   parts += [ b.rstrip ("\n") for b in keep ]

   return "\n\n".join (parts) + "\n"

def tidy_changelog (text: str) -> str:
   """Rewrite a whole CHANGELOG.md to the house shape: every bullet squeezed
   through `normalize_line`, `###` subsections that end up empty dropped,
   duplicates dropped per version. The preamble and every released version
   heading survive untouched — a release with nothing left to say still has a
   date. An empty unreleased heading is dropped; it records nothing."""
   preamble, sections = _split_sections (text)

   blocks = []
   for ver, block in sections:
      lines = block.splitlines ()
      head  = lines [0].strip ()
      body  = normalize ("\n".join (lines [1:]))

      if not body and not ver:
         continue

      blocks.append (f"{head}\n\n{body}" if body else head)

   parts = ([ preamble.strip () ] if preamble.strip () else []) + blocks

   return "\n\n".join (parts).strip () + "\n"

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
      path.write_text (f"{HEADER}\n{entry}\n")
