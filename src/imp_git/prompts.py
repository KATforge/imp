import re

from imp_git.validate import COMMIT_TYPES

_TYPES_STR = ", ".join (COMMIT_TYPES)

def _ticket_rule (branch: str) -> str:
   match = re.search (r"([A-Z]+-[0-9]+)", branch)
   if not match:
      return ""

   ticket = match.group (1)
   return f'- Include ticket {ticket} after the type, e.g. "fix: {ticket} message"\n'

def _whisper (text: str) -> str:
   if not text:
      return ""
   return f"\nUser hint: {text}\n"

def commit (diff: str, branch: str = "", whisper: str = "") -> str:
   return f"""\
Generate a Conventional Commits message for this diff.
{_whisper (whisper)}\
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

def review (diff: str, whisper: str = "") -> str:
   return f"""\
Review this code diff. Be concise and actionable.
{_whisper (whisper)}\
Check for:
- Bugs or logic errors
- Security issues
- Performance problems
- Code style issues
- Missing error handling

If the code looks good, say so briefly.

Diff:
{diff}

Output ONLY the review:"""

def split_changes (change_diffs: str, num_changes: int, branch: str = "", whisper: str = "") -> str:
   return f"""\
Group these change sections into logical commits. Each group is one commit.
{_whisper (whisper)}\
Format: type: message
Types: {_TYPES_STR}
{_ticket_rule (branch)}
Rules:
- Output a JSON array, no markdown fences, no explanation
- Each element: {{"changes": ["path#1", "path#2"], "message": "type: description"}}
- ALL LOWERCASE after the colon (except ticket IDs like IMP-123)
- Imperative mood: "add" not "added", "fix" not "fixes"
- Max 72 chars per message, no period at end
- Every change MUST appear exactly once
- There are {num_changes} changes; reference all {num_changes}
- Minimize groups while preserving logical changes
- No Co-Authored-By or AI attribution

Branch: {branch}

Changes:
{change_diffs}

Output ONLY the JSON array:"""
