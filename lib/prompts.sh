#!/bin/bash
#
# AI prompt templates
#

prompt_commit() {
   local diff="$1"
   local files

   files=$(echo "$diff" | grep -c '^diff --git' || true)

   cat << EOF
Generate a git commit message for this diff ($files files changed).

Rules:
- Subject line: imperative mood, max 50 chars, no period
- If more than one change, add a blank line then a body paragraph
- Body must be prose, not bullet points: use semicolons to separate distinct changes
- Write as a human would: natural, concise, no filler
- No markdown, no backticks, no quotes, no bullet points, no dashes
- Mention all affected areas when multiple files change

Example for a multi-change commit:
Harden AI pipeline and expand test coverage

Pipe prompts via stdin to remove argument size limits; add 120s
timeout to claude calls; strip leading blank lines in markdown
renderer; add sanitize helper for single-line AI output and apply
it to branch, fix, and stash commands.

Diff:
$diff

Output ONLY the commit message, nothing else:
EOF
}

prompt_branch() {
   cat << EOF
Suggest a git branch name for: $1

Rules:
- Lowercase, hyphens only, no spaces
- Max 30 chars
- Format: type/short-name
- Types: feat, fix, refactor, docs, test, chore

Output ONLY the branch name:
EOF
}

prompt_stash() {
   cat << EOF
Generate a short stash message. Max 50 chars, no quotes, no backticks:

$1

Output ONLY the message:
EOF
}

prompt_revert() {
   local commit_msg="$1"
   local diff="$2"

   cat << EOF
Generate a commit message for reverting this change. Start with 'Revert:'. Max 50 chars:

Original: $commit_msg

Changes reverted:
$diff

Output ONLY the commit message:
EOF
}

prompt_diff() {
   cat << EOF
Explain what these code changes do in plain English. Be concise, use bullet points for multiple changes:

$1

Output ONLY the explanation:
EOF
}

prompt_review() {
   cat << EOF
Review this code diff. Be concise and actionable.

Check for:
- Bugs or logic errors
- Security issues
- Performance problems
- Code style issues
- Missing error handling

If the code looks good, say so briefly.

Diff:
$1

Output ONLY the review:
EOF
}

prompt_describe() {
   local content="$1"
   local type="$2"

   if [[ "$type" == "diff" ]]; then
      cat << EOF
Describe what this code change does in 2-3 sentences:

$content
EOF
   else
      cat << EOF
Describe what this project has been working on based on these recent commits. 2-3 sentences:

$content
EOF
   fi
}

prompt_fix() {
   local title="$1"
   local body="$2"

   cat << EOF
Suggest a git branch name for fixing this issue:

Title: $title
Description: $body

Rules:
- Lowercase, hyphens only
- Max 30 chars
- Format: fix/<short-name>
- Include issue number if fits

Output ONLY the branch name:
EOF
}

prompt_pr() {
   local branch="$1"
   local log="$2"
   local diff="$3"

   cat << EOF
Generate a GitHub pull request title and description.

Branch: $branch
Commits:
$log

Diff summary:
$diff

Format:
TITLE: <50 char title>

DESCRIPTION:
## Summary
<2-3 bullet points>

## Changes
<list main changes>

Output ONLY in this format:
EOF
}

prompt_changelog() {
   local log="$1"
   local diff="$2"

   cat << EOF
Generate a changelog entry from these code changes.

Use the diff as the primary source of truth. The commit messages are for context only.
Be thorough: every meaningful change should have its own line.

Each line must start with a prefix: Added, Changed, Fixed, or Removed.
Format: "- Added: description" or "- Fixed: description"
Skip prefixes that don't apply. Be specific about what changed. No commit hashes.

Commits:
$log

Diff:
$diff

Output ONLY the changelog lines:
EOF
}

prompt_release_summary() {
   cat << EOF
Write a git commit subject line for these changes. Max 50 chars, imperative mood, no quotes, no markdown, no period:

$1

Output ONLY the subject line:
EOF
}

prompt_gitignore() {
   cat << EOF
Generate a .gitignore for this project based on the files present:

$1

Output ONLY the .gitignore content, no explanation:
EOF
}
