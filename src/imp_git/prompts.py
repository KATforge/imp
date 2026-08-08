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
   num_files: int,
   branch: str,
   whisper: str,
   preamble: str = "",
) -> str:
   return f"""\
{header}
{preamble}{_whisper (whisper)}\
Format: type: message
Types: {_TYPES_STR}
{_ticket_rule (branch)}
Rules:
- Output a JSON array, no markdown fences, no explanation
- Each element: {{"files": ["path1", "path2"], "message": "type: description"}}
- ALL LOWERCASE after the colon (except ticket IDs like IMP-123)
- Imperative mood: "add" not "added", "fix" not "fixes"
- Max 72 chars per message, no period at end
- CRITICAL: every file MUST appear in exactly one group.
- There are {num_files} files; your output must reference all {num_files}.
- Minimize number of groups (prefer fewer, larger groups)
- Group by logical change, not by directory

Branch: {branch}

{content_label}:
{content}

Output ONLY the JSON array:"""

def split (file_diffs: str, num_files: int, branch: str = "", whisper: str = "") -> str:
   return _split_prompt (
      "Group these changed files into logical commits. Each group = one commit.",
      "File diffs",
      file_diffs,
      num_files,
      branch,
      whisper,
   )

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

def split_plan (file_stats: str, branch: str = "", whisper: str = "") -> str:
   num_files = len (file_stats.splitlines ())

   return _split_prompt (
      f"Group these {num_files} changed files into logical commits. Each group = one commit.",
      "File stats (lines added / lines removed / path)",
      file_stats,
      num_files,
      branch,
      whisper,
   )

def split_retry (
   content_label: str,
   content: str,
   prev_response: str,
   missing: list [str],
   extra: list [str],
   num_files: int,
   branch: str = "",
   whisper: str = "",
) -> str:
   diag = "\nYour previous output was rejected. Fix it.\n\nPrevious output:\n"
   diag += prev_response.strip () + "\n"

   if missing:
      diag += "\nFiles you DROPPED (must appear in exactly one group):\n"
      diag += "\n".join (f"- {f}" for f in missing) + "\n"

   if extra:
      diag += "\nFiles you INVENTED (remove these):\n"
      diag += "\n".join (f"- {f}" for f in extra) + "\n"

   return _split_prompt (
      "Re-group these changed files into logical commits. Each group = one commit.",
      content_label,
      content,
      num_files,
      branch,
      whisper,
      preamble=diag,
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

_EXPLAIN_MODES = {
   "brief": "Be terse. 1-3 sentences total. Prefer prose over bullets. No headings.",
   "balanced": "Be concise. 1 short paragraph summary, then 2-5 bullets of notable specifics if useful.",
   "full": "Be thorough. Walk through the change file-by-file. Call out motivation, risks, and follow-ups.",
}

def explain (diff: str, mode: str = "balanced", whisper: str = "") -> str:
   style = _EXPLAIN_MODES.get (mode, _EXPLAIN_MODES ["balanced"])

   return f"""\
Explain this code change in plain English. Audience: a developer who has not read the diff.
{_whisper (whisper)}\
Style: {style}

Cover what changed and why (the intent), not a line-by-line readout. Skip noise
(formatting, import reordering, generated files). Use markdown. No code fences
around the whole response.

Diff:
{diff}

Output ONLY the explanation:"""

def history (log: str, patches: str, path: str = "") -> str:
   subject = f"the history of `{path}`" if path else "this repository history"

   return f"""\
Explain {subject}. Focus on how the code evolved, why the major changes likely
happened, and any recurring areas of risk. Be concise and use markdown.

Commit history:
{log}

Relevant patches:
{patches}

Output ONLY the explanation:"""

def grep_pattern (question: str) -> str:
   return f"""\
Convert this code-search question into one extended regular expression suitable
for `git grep -E`. Prefer identifiers and exact technical terms over broad words.

Question: {question}

Output ONLY the regular expression, without quotes or markdown fences:"""

def grep_summary (question: str, pattern: str, matches: str) -> str:
   return f"""\
Answer the code-search question using only these matches. Explain where the
relevant behavior lives and identify the best files to inspect next. Be concise.

Question: {question}
Pattern: {pattern}

Matches:
{matches}

Output ONLY the answer in markdown:"""

def fixup_pick (staged: str, candidates: str) -> str:
   return f"""\
Given a staged change and a list of recent commits, decide which commit the change
most likely fixes up. Score 0-100 (100 = certain). If no commit is a clear
target, return a low score.

Staged change:
{staged}

Recent commits (newest first, each as "<hash> <subject>" followed by its diff):
{candidates}

Rules:
- Output a JSON object, no markdown fences, no explanation
- Shape: {{"best": "<full-or-prefix-hash>", "score": 0-100, "reason": "<short>",
  "alternates": [{{"sha": "<hash>", "score": 0-100, "reason": "<short>"}}]}}
- "best" must be one of the candidate hashes above
- alternates: up to 3 next-best candidates, may be empty array
- Match on file overlap, line proximity, and topical similarity

Output ONLY the JSON object:"""

def stash_title (diff: str) -> str:
   return f"""\
Summarize this work-in-progress diff as a short stash title.

Rules:
- 5 to 12 words
- Lowercase, no trailing period
- Imperative mood ("add x", "fix y")
- No quotes, no markdown, no prefix like "wip:" or "stash:"
- Capture the dominant change, not every file

Diff:
{diff}

Output ONLY the title:"""

def rescue_rank (candidates: str, hint: str = "") -> str:
   hint_block = ""
   if hint:
      hint_block = f"\nUser hint (filter / bias toward this topic): {hint}\n"

   return f"""\
Rank these orphaned or recently-moved-past commits by their likely value as
recovery targets. Higher score = more likely to be lost work worth restoring.
{hint_block}
Candidates (each with sha, age, subject, file stat):
{candidates}

Rules:
- Output a JSON array, no markdown fences, no explanation
- Each element: {{"sha": "<hash>", "score": 0-100, "what": "<one-line description of what this looks like>"}}
- Order: highest score first
- Bias against tiny / mechanical commits (single line touched, formatting only)
- Bias toward commits with meaningful subjects and substantive diffs
- Limit to top 10

Output ONLY the JSON array:"""

def standup (commits: str, author: str = "", since: str = "") -> str:
   meta = []
   if author:
      meta.append (f"author: {author}")
   if since:
      meta.append (f"since: {since}")
   meta_line = ("\n" + "\n".join (meta) + "\n") if meta else ""

   return f"""\
Write a standup-style summary of recent work from these commits.
{meta_line}
Commits (oldest first, "<hash> <date> <subject>"):
{commits}

Rules:
- Output markdown
- Group commits by theme (3-5 themes at most); skip themes with only trivial commits
- For each theme: a one-line header ("**theme name**") then 1-3 short bullets
- Cite hashes in parentheses at end of bullets, like "(a1b2c3d)"
- Skip release / version-bump / changelog noise
- No greeting, no closing, no headings other than the theme names

Output ONLY the summary:"""

MAX_WORDS = 8

def changelog_entry (diffs: str) -> str:
   return f"""\
Analyze these git commit diffs and produce a changelog entry.

Every line is a terse one-liner. A changelog is scanned, not read: uniform
shape matters more than detail, and the reader can always open the diff.

Line rules, no exceptions:
- Start with a plain present-tense verb: Add, Fix, Change, Remove, Rename, Move, Speed up
- {MAX_WORDS} words maximum, and fewer is better
- Name the user-visible thing that changed, nothing else
- No explanation, justification, or outcome: no "so that", "which lets", "in order to", "for better X"
- No implementation detail: no file paths, function names, class names, internals
- No parentheses, no dashes introducing a clause, no trailing period
- Merge related small changes into one line
- One line per change, prefix with "- "
- Skip trivial changes (whitespace, formatting, import reordering)
- Skip release/changelog commits themselves

Write like this:
- Add oauth login
- Fix crash on empty config
- Remove legacy token endpoint

Never like this:
- Added a new OAuth login flow to the auth service so users can sign in with Google
- Refactored TokenRepository (src/token.py) to use a cleaner abstraction

Categorize every meaningful change as Added, Changed, Removed, or Fixed, and
output sections in this exact format (omit empty sections):

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

def docs_changes (diffs: str) -> str:
   return f"""\
Summarize what changed in this diff, focused ONLY on things that could affect
user-facing documentation: new/renamed/removed commands, flags, options,
endpoints, config keys, defaults, response shapes, status codes, or behavior.

Rules:
- Output a short markdown bullet list, one concrete fact per line
- State the change precisely: "added command `imp docs`", "renamed flag --foo to --bar",
  or "changed default of X from a to b"
- Ignore internal refactors, tests, and formatting that expose no documented surface
- If nothing could affect documentation, output exactly: NONE

Diff:
{diffs}

Output ONLY the bullet list, or NONE:"""

def docs_select (summary: str, manifest: str) -> str:
   return f"""\
Given a change summary and a list of documentation files (path then headings),
choose which files this change could make inaccurate or incomplete.

Change summary:
{summary}

Documentation files:
{manifest}

Rules:
- Output a JSON array of file paths, no markdown fences, no explanation
- Include a path only if the change plausibly affects its content
- Prefer precision: an empty array [] is correct when nothing is affected

Output ONLY the JSON array:"""

def docs_edit (summary: str, path: str, content: str, mode: str = "reconcile") -> str:
   scope = (
      "Only ADD documentation for genuinely new surface. Do not alter existing prose."
      if mode == "additive" else
      "Correct statements the change contradicts, and add documentation for new surface. "
      "Do not restyle prose that is still accurate."
   )

   return f"""\
Update this documentation page so it matches the change described. {scope}

Change summary:
{summary}

File: {path}

Rules:
- Return the COMPLETE updated file, nothing else, no markdown fences
- Change only what the summary makes inaccurate or missing
- Preserve the file's existing voice, structure, headings, and formatting
- Never invent behavior the summary does not state
- If the page is already accurate and complete, output exactly: NO CHANGE

Current contents:
{content}

Output the full updated file, or NO CHANGE:"""

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
