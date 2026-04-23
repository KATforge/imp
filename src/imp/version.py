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
