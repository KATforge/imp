import re
from pathlib import Path

from imp_git import validate
from imp_git.validate import COMMIT_RE, TYPES_PATTERN

MAX_WORDS = 8

# Every release bullet is squeezed through `normalize_line` before it reaches
# the release notes. Uniform one-liners keep them easy to scan.
_TYPE_PREFIX = re.compile (
   rf"^(?:(?:{TYPES_PATTERN})(\(.+?\))?!?"
   r"|added|changed|deprecated|removed|fixed|security)"
   r":\s*",
   re.I,
)
_PAREN       = re.compile (r"\s*\([^()]*\)")
_SENTENCE    = re.compile (r"(?<=[a-z0-9])\.\s+\S")
_TAIL        = re.compile (
   r"\s+(?:[-\u2013\u2014]\s|so\s|in order to\b|instead of\b|rather than\b"
   r"|which\b|allowing\b|ensuring\b|enabling\b)"
   r"|,\s+(?:so|which|because|allowing|ensuring|enabling)\b",
   re.I,
)

def _capitalize (text: str) -> str:
   return text [0].upper () + text [1:] if len (text) > 1 else text

def _lower_first (text: str) -> str:
   """Lowercase a leading ordinary word, leaving acronyms and identifiers alone."""

   head = text.split (" ", 1) [0]
   if not head [:1].isupper () or head [1:] != head [1:].lower ():
      return text

   return text [0].lower () + text [1:]

def normalize_line (text: str) -> str:
   """One changelog bullet, normalized to the house shape: no commit-type
   prefix, no parenthetical aside, no explanatory tail, one sentence, no
   trailing punctuation, capitalized. Returns "" when nothing survives."""
   text = _TYPE_PREFIX.sub ("", re.sub (r"\s+", " ", text.strip ().lstrip ("-*").strip ()))

   if not validate.publishable (text):
      return ""

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
   if len (words) > MAX_WORDS:
      head = " ".join (words).split (",") [0].split ()
      if len (head) >= 3:
         words = head

   text = " ".join (words).rstrip (" .,;:")

   return _capitalize (text) if text else ""

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

_STABLE_TAG = re.compile (r"^v\d+\.\d+\.\d+$")

def highest (names: list [str]) -> str:
   """Return the highest stable release tag among names, ignoring anything else."""

   ranked = [ (base_tuple (name), name) for name in names if _STABLE_TAG.match (name) ]

   return max (ranked) [1] if ranked else ""

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
   entries = []
   seen = set ()

   for line in subjects.splitlines ():
      line = line.strip ()
      if not line:
         continue

      match = COMMIT_RE.match (line)
      kind = match.group (1) if match else ""
      desc = normalize_line (match.group (3) if match else line)

      if not desc or desc.lower () in seen:
         continue

      seen.add (desc.lower ())

      if kind == "feat":
         desc = re.sub (r"^(?:add|added)\s+", "", desc, flags=re.I)
         entries.append (f"- Added {_lower_first (desc) if desc else 'the change'}")
      elif kind == "fix":
         desc = re.sub (r"^(?:fix|fixed|prevent|prevented)\s+", "", desc, flags=re.I)
         entries.append (f"- Fixed {_lower_first (desc) if desc else 'the issue'}")
      else:
         desc = re.sub (r"^(?:change|changed|update|updated)\s+", "", desc, flags=re.I)
         entries.append (f"- Changed {_lower_first (desc) if desc else 'the implementation'}")

   return "\n".join (entries)

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

def _write_version (path: Path, new_version: str) -> bool:
   if not path.is_file ():
      return False

   text = path.read_text ()
   new_text, n = _pattern_for (path).subn (rf"\g<1>{new_version}\g<3>", text, count=1)

   if n == 0 or new_text == text:
      return False

   path.write_text (new_text)
   return True

def sync_manifests (root: Path, new_version: str) -> list [Path]:
   """Write the release version into every manifest the repo carries.
   Returns the paths that changed. Manifests without a version field are
   left alone — keeps imp git-generic."""
   return [ p for p in manifest_paths (root) if _write_version (p, new_version) ]

