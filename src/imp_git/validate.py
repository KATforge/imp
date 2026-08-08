import re

COMMIT_TYPES = (
   "feat", "fix", "refactor", "build", "chore",
   "docs", "test", "style", "perf", "ci",
)

TYPES_PATTERN = "|".join (COMMIT_TYPES)

COMMIT_RE = re.compile (
   rf"^({TYPES_PATTERN})"
   r"(\([a-z0-9._/-]+\))?!?: (.+)$"
)

_TICKET_RE = re.compile (r"^[A-Z]+-[0-9]")

_BRANCH_RE = re.compile (r"^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$")

_ATTRIBUTION_SOURCE = (
   r"(?:ai(?: agent)?|artificial intelligence(?: agent)?|llm|language model|bot|chatgpt|"
   r"claude(?: code)?|codex|gemini|(?:github )?copilot|openai(?: codex)?|anthropic)"
)

_ATTRIBUTION_REF = rf"(?:\[{_ATTRIBUTION_SOURCE}\](?:\([^\n)]+\))?|{_ATTRIBUTION_SOURCE})"

_ATTRIBUTION_RES = (
   re.compile (r"(?im)^\s*co-authored-by\s*:.*$"),
   re.compile (
      rf"(?im)^\s*(?:authored|created|generated|assisted)-by\s*:\s*"
      rf".*\b{_ATTRIBUTION_SOURCE}\b.*$"
   ),
   re.compile (
      rf"(?im)^\s*(?:[-*>#]+\s*)?(?:🤖\s*)?"
      rf"(?:(?:this|the)\s+(?:change|commit|pull request|pr|code|file|document|documentation|"
      rf"changelog|release(?: notes)?)\s+(?:was|is)\s+)?"
      rf"(?:(?:co-)?authored|built|created|developed|generated|made|produced|written|assisted)"
      rf"\s+(?:by|using|with)\s+(?:an?\s+)?{_ATTRIBUTION_REF}"
      r"(?:\s*[.!])?\s*$"
   ),
   re.compile (
      rf"(?im)^\s*(?:[-*>#]+\s*)?(?:made|developed|written)?\s*with\s+"
      rf"(?:help|assistance)\s+from\s+{_ATTRIBUTION_REF}(?:\s*[.!])?\s*$"
   ),
   re.compile (
      rf"(?im)^\s*(?:[-*>#]+\s*)?(?:ai|artificial intelligence)[ -]"
      rf"(?:assisted|authored|generated)(?:\s+(?:by|using|with)\s+{_ATTRIBUTION_REF})?"
      r"(?:\s*[.!])?\s*$"
   ),
   re.compile (
      rf"(?im)^\s*(?:[-*>#]+\s*)?(?:🤖\s*)?{_ATTRIBUTION_REF}\s+"
      rf"(?:assisted|authored|created|generated|helped|wrote)\b.*\b"
      r"(?:change|commit|code|document|documentation|file|pull request|release notes)\b"
      r"(?:\s*[.!])?\s*$"
   ),
)

_ACTOR_RE = re.compile (
   r"(?i)(?<![a-z0-9._-])actor:[a-z0-9.-]+:[a-z0-9.-]+(?:[:][a-z0-9.-]+)*(?![a-z0-9._-])"
)

def _provenance (text: str) -> list [str]:
   matches = [
      match.group (0).strip ().casefold ()
      for pattern in _ATTRIBUTION_RES
      for match in pattern.finditer (text)
   ]
   matches.extend (match.group (0).casefold () for match in _ACTOR_RE.finditer (text))

   return matches

def publishable (text: str) -> bool:
   """Whether text omits AI attribution and private actor IDs."""
   return not _provenance (text)

def commit (msg: str, max_subject: int = 72) -> bool:
   subject = msg.split ("\n", 1) [0]

   if len (subject) > max_subject or not COMMIT_RE.match (subject):
      return False
   if not publishable (msg):
      return False

   parts = subject.split (": ", 1)
   if len (parts) < 2 or not parts [1]:
      return False

   desc = parts [1]
   if desc.endswith ("."):
      return False
   return not (desc [0].isupper () and not _TICKET_RE.match (desc))
