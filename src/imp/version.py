import re


def bump (current: str, level: str) -> str:
   match = re.match (r"^(\d+)\.(\d+)\.(\d+)$", current)
   if not match:
      return level

   major = int (match.group (1))
   minor = int (match.group (2))
   patch = int (match.group (3))

   if level == "major":
      return f"{major + 1}.0.0"
   elif level == "minor":
      return f"{major}.{minor + 1}.0"
   elif level == "patch":
      return f"{major}.{minor}.{patch + 1}"

   return level


def changelog_from_commits (subjects: str) -> str:
   added = []
   fixed = []
   changed = []

   pattern = re.compile (
      r"^(feat|fix|refactor|build|chore|docs|test|style|perf|ci)"
      r"(\(.+\))?!?: (.+)$"
   )

   for line in subjects.splitlines ():
      line = line.strip ()
      if not line:
         continue

      if re.match (r"^[0-9a-f]+ ", line):
         line = line.split (" ", 1) [1]

      match = pattern.match (line)
      if match:
         kind = match.group (1)
         desc = match.group (3)
      else:
         desc = line [0].upper () + line [1:] if len (line) > 1 else line
         changed.append (f"- {desc}")
         continue

      desc = desc [0].upper () + desc [1:] if len (desc) > 1 else desc

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
