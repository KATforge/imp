import re


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
Types: feat, fix, refactor, build, chore, docs, test, style, perf, ci
{_ticket_rule (branch)}
Rules:
- Subject only, one line, max 72 chars, no period
- ALL LOWERCASE after the colon (except ticket IDs like IMP-123)
- Imperative mood: "add" not "added", "fix" not "fixes"
- Pick the type that best fits the primary change
- No markdown, no backticks, no quotes
- No body, no bullet points, just the subject line
- Output will be validated against commitlint rules; it must pass

Diff:
{diff}

Output ONLY the commit message, nothing else:"""


def review (diff: str) -> str:
   return f"""\
Review this code diff. Be concise and actionable.

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


def branch_name (description: str) -> str:
   return f"""\
Suggest a git branch name for: {description}

Rules:
- Lowercase, hyphens only, no spaces
- Max 30 chars
- Format: type/short-name
- Types: feat, fix, refactor, docs, test, chore

Output ONLY the branch name:"""


def revert (commit_msg: str, diff: str) -> str:
   return f"""\
Generate a commit message for reverting this change. Start with 'Revert:'. Max 50 chars:

Original: {commit_msg}

Changes reverted:
{diff}

Output ONLY the commit message:"""


def fix (title: str, body: str) -> str:
   return f"""\
Suggest a git branch name for fixing this issue:

Title: {title}
Description: {body}

Rules:
- Lowercase, hyphens only
- Max 30 chars
- Format: fix/<short-name>
- Include issue number if fits

Output ONLY the branch name:"""


def pr (branch: str, log: str, diff: str) -> str:
   return f"""\
Generate a GitHub pull request title and description.

Branch: {branch}
Commits:
{log}

Diff summary:
{diff}

Format:
TITLE: <50 char title>

DESCRIPTION:
## Summary
<2-3 bullet points>

## Changes
<list main changes>

Output ONLY in this format:"""


def split (file_diffs: str, branch: str = "") -> str:
   return f"""\
Group these changed files into logical commits. Each group = one commit.

Format: type: message
Types: feat, fix, refactor, build, chore, docs, test, style, perf, ci
{_ticket_rule (branch)}
Rules:
- Output a JSON array, no markdown fences, no explanation
- Each element: {{"files": ["path1", "path2"], "message": "type: description"}}
- ALL LOWERCASE after the colon (except ticket IDs like IMP-123)
- Imperative mood: "add" not "added", "fix" not "fixes"
- Max 72 chars per message, no period at end
- Every file must appear in exactly one group
- Minimize number of groups (prefer fewer, larger groups)
- Group by logical change, not by directory

Branch: {branch}

File diffs:
{file_diffs}

Output ONLY the JSON array:"""
