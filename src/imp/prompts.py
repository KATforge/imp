import re


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


def branch_name (description: str, whisper: str = "") -> str:
   return f"""\
Suggest a git branch name for: {description}
{_whisper (whisper)}\
Rules:
- Lowercase, hyphens only, no spaces
- Max 30 chars
- Format: type/short-name
- Types: feat, fix, refactor, docs, test, chore

Output ONLY the branch name:"""


def revert (commit_msg: str, diff: str, whisper: str = "") -> str:
   return f"""\
Generate a commit message for reverting this change. Start with 'Revert:'. Max 50 chars:
{_whisper (whisper)}\
Original: {commit_msg}

Changes reverted:
{diff}

Output ONLY the commit message:"""


def fix (title: str, body: str, whisper: str = "") -> str:
   return f"""\
Suggest a git branch name for fixing this issue:
{_whisper (whisper)}\
Title: {title}
Description: {body}

Rules:
- Lowercase, hyphens only
- Max 30 chars
- Format: fix/<short-name>
- Include issue number if fits

Output ONLY the branch name:"""


def pr (branch: str, log: str, diff: str, whisper: str = "") -> str:
   return f"""\
Generate a GitHub pull request title and description.
{_whisper (whisper)}\
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


def split (file_diffs: str, branch: str = "", whisper: str = "") -> str:
   return f"""\
Group these changed files into logical commits. Each group = one commit.
{_whisper (whisper)}\
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


def split_plan (file_stats: str, branch: str = "", whisper: str = "") -> str:
   num_files = len (file_stats.splitlines ())

   return f"""\
Group these {num_files} changed files into logical commits. Each group = one commit.
{_whisper (whisper)}\
Format: type: message
Types: feat, fix, refactor, build, chore, docs, test, style, perf, ci
{_ticket_rule (branch)}
Rules:
- Output a JSON array, no markdown fences, no explanation
- Each element: {{"files": ["path1", "path2"], "message": "type: description"}}
- ALL LOWERCASE after the colon (except ticket IDs like IMP-123)
- Imperative mood: "add" not "added", "fix" not "fixes"
- Max 72 chars per message, no period at end
- CRITICAL: every single file below MUST appear in exactly one group. There are {num_files} files; your output must reference all {num_files}
- Minimize number of groups (prefer fewer, larger groups)
- Group by logical change, not by directory

Branch: {branch}

File stats (lines added / lines removed / path):
{file_stats}

Output ONLY the JSON array:"""


def resolve (content: str, path: str, ours: str, theirs: str, whisper: str = "") -> str:
   return f"""\
Resolve all merge conflicts in this file.
{_whisper (whisper)}\
Branches:
- Ours (current): {ours}
- Theirs (incoming): {theirs}

File: {path}

Rules:
- Resolve every conflict marked by <<<<<<<, =======, >>>>>>>
- Preserve all non-conflicted code exactly as-is
- Output the complete resolved file, nothing else
- No explanation, no markdown fences, no commentary

{content}

Output ONLY the resolved file:"""


def changelog_infer (subjects: str) -> str:
   return f"""\
Group these git commit subjects into logical version releases.
These commits have no git tags, so infer where version boundaries should be.

Rules:
- Output a JSON array, no markdown fences, no explanation
- Each element: {{"version": "0.0.X", "commits": ["subject1", "subject2"]}}
- Start numbering from 0.0.1 unless told otherwise
- Group by logical release boundaries (look for "release" commits, large feature batches, or natural breakpoints)
- Every commit must appear in exactly one group
- Order chronologically (earliest version first)

Commits (oldest first):
{subjects}

Output ONLY the JSON array:"""
