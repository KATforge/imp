import re

from imp_git.validate import COMMIT_TYPES

_TYPES_STR = ", ".join (COMMIT_TYPES)

def _ticket_rule (branch: str) -> str:
   match = re.search (r"([A-Z]+-[0-9]+)", branch)
   if not match:
      return ""

   ticket = match.group (1)
   return f'- Include ticket {ticket} after the type, e.g. "fix: {ticket} message"\n'

def commit (diff: str, branch: str = "") -> str:
   return f"""\
Generate a Conventional Commits message for this diff.
Format: type: message
Types: {_TYPES_STR}
{_ticket_rule (branch)}
Rules:
- Subject only, one line, max 72 chars, no period
- ALL LOWERCASE after the colon (except ticket IDs like IMP-123)
- Imperative mood: "add" not "added", "fix" not "fixes"
- Pick the type that best fits the primary change
- No markdown, no backticks, no quotes
- No body, no bullet points, just the subject line
- No Co-Authored-By or AI attribution
- Output will be validated against commitlint rules; it must pass

Diff:
{diff}

Output ONLY the commit message, nothing else:"""

def review (diff: str) -> str:
   return f"""\
Review this diff as a precise senior engineer.

Return ONLY a JSON object, no prose, in this shape:
{{"summary": "<two or three sentences on what the change does and its overall quality>",
  "annotations": [{{"file": "<path>", "line": <new-file line number or null>,
                    "severity": "info|warn|risk", "note": "<one concise sentence>"}}]}}

Rules:
- Annotate only what matters: bugs, risks, contract changes, and notable design choices
- Prefer few strong annotations over many weak ones; zero is a valid answer
- "risk" means likely defect or data loss; "warn" means questionable; "info" means noteworthy
- line refers to the NEW file, taken from the hunk headers

Diff:
{diff}"""

def answer (diff: str, question: str) -> str:
   return f"""\
Answer a question about this diff as a precise senior engineer.
Be direct and concrete; reference files and lines from the diff. Plain text, no preamble.

Diff:
{diff}

Question: {question}"""

def verdict (name: str, age: str, diff: str) -> str:
   return f"""\
Judge one in-progress feature branch against trunk and return ONLY a JSON object:
{{"verdict": "integrate|discard|hold", "reason": "<one concise sentence>"}}

- integrate: the change is coherent, complete, and safe to land as-is
- discard: empty, abandoned, superseded, or plainly not worth keeping
- hold: incomplete, risky, or you are not confident; when in doubt, hold

Feature: {name} (age {age})

Diff against trunk (includes uncommitted work):
{diff}"""
