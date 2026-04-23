import re

from imp.validate import COMMIT_TYPES

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
- Output will be validated against commitlint rules; it must pass

Diff:
{diff}

Output ONLY the commit message, nothing else:"""

def gitignore (files: str, existing: str = "") -> str:
   existing_section = ""
   if existing:
      existing_section = f"""
Existing .gitignore contents (do not duplicate these):
{existing}
"""

   return f"""\
Generate .gitignore entries for this project.
{existing_section}
Project files:
{files}

Rules:
- Detect the language/framework from the file names
- Include standard ignore patterns for the detected stack
- Include OS files (.DS_Store, Thumbs.db)
- Include editor files (.vscode, .idea)
- One entry per line, no comments, no blank lines
- Do not include entries already in the existing .gitignore
- If nothing new to add, output NONE

Output ONLY the .gitignore entries, nothing else:"""

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

_BRANCH_TYPES = "feat, fix, refactor, docs, test, chore"

def branch_name (description: str, whisper: str = "") -> str:
   return f"""\
Suggest a git branch name for: {description}
{_whisper (whisper)}\
Rules:
- Lowercase, hyphens only, no spaces
- Max 30 chars
- Format: type/short-name
- Types: {_BRANCH_TYPES}

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

def _split_prompt (
   header: str,
   content_label: str,
   content: str,
   branch: str,
   whisper: str,
   extra_rules: str = "",
) -> str:
   return f"""\
{header}
{_whisper (whisper)}\
Format: type: message
Types: {_TYPES_STR}
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
{extra_rules}
Branch: {branch}

{content_label}:
{content}

Output ONLY the JSON array:"""

def split (file_diffs: str, branch: str = "", whisper: str = "") -> str:
   return _split_prompt (
      "Group these changed files into logical commits. Each group = one commit.",
      "File diffs",
      file_diffs,
      branch,
      whisper,
   )

def split_plan (file_stats: str, branch: str = "", whisper: str = "") -> str:
   num_files = len (file_stats.splitlines ())

   return _split_prompt (
      f"Group these {num_files} changed files into logical commits. Each group = one commit.",
      "File stats (lines added / lines removed / path)",
      file_stats,
      branch,
      whisper,
      f"- CRITICAL: every single file below MUST appear in exactly one group. There are {num_files} files; your output must reference all {num_files}\n",
   )

def _bias (favor: str, ours: str, theirs: str) -> str:
   if not favor:
      return ""

   if favor == "ours":
      return f"""
Bias: STRONGLY favor ours ({ours}). This branch is more up to date.
When in doubt, prefer ours. Only take from theirs ({theirs}) when it
introduces something clearly new that does not conflict with our intent.
"""

   return f"""
Bias: STRONGLY favor theirs ({theirs}). That branch is more up to date.
When in doubt, prefer theirs. Only keep from ours ({ours}) when it
introduces something clearly new that does not conflict with their intent.
"""

def resolve (content: str, path: str, ours: str, theirs: str, whisper: str = "", favor: str = "") -> str:
   return f"""\
Resolve all merge conflicts in this file.
{_whisper (whisper)}\
{_bias (favor, ours, theirs)}\
Branches:
- Ours (current): {ours}
- Theirs (incoming): {theirs}

File: {path}

Rules:
- Resolve every conflict marked by <<<<<<<, =======, >>>>>>>
- Preserve all non-conflicted code exactly as-is
- No markdown fences

Output in two sections separated by exactly "---RESOLVED---" on its own line:

SECTION 1 (reasoning): For each conflict, explain briefly:
- What ours ({ours}) has vs what theirs ({theirs}) has (one line each)
- Which you picked or how you merged, and why

SECTION 2 (resolved file): The complete resolved file, nothing else

Example format:
Conflict 1 (lines 10-20):
  Ours ({ours}): adds validation for email field
  Theirs ({theirs}): renames validate() to check()
  Resolution: kept both; applied rename and preserved validation

---RESOLVED---
<complete file contents>

{content}

Output:"""

def resolve_revise (
   content: str,
   path: str,
   ours: str,
   theirs: str,
   previous_result: str,
   previous_reasoning: str,
   feedback: str,
   favor: str = "",
) -> str:
   return f"""\
Revise your merge conflict resolution based on user feedback.
{_bias (favor, ours, theirs)}\
Branches:
- Ours (current): {ours}
- Theirs (incoming): {theirs}

File: {path}

Original file with conflicts:
{content}

Your previous reasoning:
{previous_reasoning}

Your previous resolution:
{previous_result}

User feedback: {feedback}

Rules:
- Address the user's feedback in your revised resolution
- Resolve every conflict marked by <<<<<<<, =======, >>>>>>>
- Preserve all non-conflicted code exactly as-is
- No markdown fences

Output in two sections separated by exactly "---RESOLVED---" on its own line:

SECTION 1 (reasoning): For each conflict, explain briefly:
- What ours ({ours}) has vs what theirs ({theirs}) has (one line each)
- Which you picked or how you merged, and why
- What changed from your previous suggestion based on the feedback

SECTION 2 (resolved file): The complete resolved file, nothing else

Output:"""

def tidy (commits: str, branch: str = "", whisper: str = "") -> str:
   return f"""\
Propose a cleanup plan for this commit history.
{_whisper (whisper)}\
Format: type: message
Types: {_TYPES_STR}
{_ticket_rule (branch)}
Rules:
- Output a JSON array, no markdown fences, no explanation
- Each element: {{"action": "keep|reword|squash|drop", "hashes": ["<hash>", ...], "message": "<new message or empty>"}}
- "keep": one hash, message empty, preserves original message
- "reword": one hash, new Conventional Commits message
- "squash": 2+ consecutive hashes, one new message covering all changes
- "drop": one hash, message empty, removes the commit entirely
- Every commit below MUST appear in exactly one group
- Preserve the original chronological order, no reordering across groups
- Squash obvious fixup/wip/typo commits into their logical parent
- Reword vague messages (wip, fix stuff, update, asdf) into proper Conventional Commits
- Drop a commit only if it is pure noise (e.g. accidental, immediately reverted)
- ALL LOWERCASE after the colon (except ticket IDs like IMP-123)
- Imperative mood, max 72 chars, no period
- Prefer keep over reword when the original is already good

Commits (oldest first, "<hash> <subject>"):
{commits}

Output ONLY the JSON array:"""

def tidy_date (expr: str) -> str:
   return f"""\
Convert this natural-language time reference to an absolute date.

Expression: {expr}

Rules:
- Output ONLY an ISO 8601 date (YYYY-MM-DD), nothing else
- Interpret relative to today
- If ambiguous, pick the most common interpretation
- No explanation, no quotes, no prose

Output:"""

def changelog_entry (diffs: str) -> str:
   return f"""\
Analyze these git commit diffs and produce a changelog entry.

Rules:
- Categorize every meaningful change as Added, Changed, Removed, or Fixed
- Describe what changed from a user's perspective, not implementation details
- One line per change, prefix with "- "
- Merge related small changes into a single line
- Skip trivial changes (whitespace, formatting, import reordering)
- Skip release/changelog commits themselves
- Output sections in this exact format (omit empty sections):

### Added
- description

### Changed
- description

### Removed
- description

### Fixed
- description

Diffs:
{diffs}

Output ONLY the changelog sections, nothing else:"""

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
