#!/bin/bash
#
# AI prompt templates
#

prompt_commit() {
   cat << EOF
Generate a git commit message for this diff.

Rules:
- First line: imperative mood, max 50 chars
- No markdown, no backticks, no quotes
- Focus on WHY not WHAT

Diff:
$1

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
      echo "Describe what this code change does in 2-3 sentences:

$content"
   else
      echo "Describe what this project has been working on based on these recent commits. 2-3 sentences:

$content"
   fi
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
   cat << EOF
Generate a changelog entry from these commits.

Use Keep a Changelog format with sections (skip empty ones):
### Added
### Changed
### Fixed
### Removed

Be concise. No commit hashes.

Commits:
$1

Output ONLY the changelog sections:
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
