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
