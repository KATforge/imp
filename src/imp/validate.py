import re

_COMMIT_RE = re.compile (
   r"^(feat|fix|refactor|build|chore|docs|test|style|perf|ci)"
   r"(\(.+\))?!?: .+"
)

_TICKET_RE = re.compile (r"^[A-Z]+-[0-9]")

_BRANCH_RE = re.compile (r"^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$")


def commit (msg: str) -> bool:
   subject = msg.split ("\n", 1) [0]

   if not _COMMIT_RE.match (subject):
      return False

   desc = subject.split (": ", 1) [1]
   if desc [0].isupper () and not _TICKET_RE.match (desc):
      return False

   return True


def branch (name: str) -> bool:
   return bool (_BRANCH_RE.match (name))
