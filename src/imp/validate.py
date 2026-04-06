import re

COMMIT_TYPES = (
   "feat", "fix", "refactor", "build", "chore",
   "docs", "test", "style", "perf", "ci",
)

TYPES_PATTERN = "|".join (COMMIT_TYPES)

COMMIT_RE = re.compile (
   rf"^({TYPES_PATTERN})"
   r"(\(.+\))?!?: (.+)$"
)

_TICKET_RE = re.compile (r"^[A-Z]+-[0-9]")

_BRANCH_RE = re.compile (r"^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$")


def commit (msg: str) -> bool:
   subject = msg.split ("\n", 1) [0]

   if not COMMIT_RE.match (subject):
      return False

   parts = subject.split (": ", 1)
   if len (parts) < 2 or not parts [1]:
      return False

   desc = parts [1]
   return not (desc [0].isupper () and not _TICKET_RE.match (desc))


def branch (name: str) -> bool:
   return bool (_BRANCH_RE.match (name))
