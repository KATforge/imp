import re

from imp_git.validate import COMMIT_TYPES

_TYPES_STR = ", ".join (COMMIT_TYPES)

def _ticket_rule (branch: str, ticket: str = "") -> str:
   match = re.search (r"([A-Z]+-[0-9]+)", ticket or branch)
   if not match:
      return ""

   value = match.group (1)
   return f'- Include ticket {value} after the type, e.g. "fix: {value} message"\n'

def commit (diff: str, branch: str = "", ticket: str = "") -> str:
   return f"""\
Generate a Conventional Commits message for this diff.
Format: type: message
Types: {_TYPES_STR}
{_ticket_rule (branch, ticket)}
Rules:
- Subject only, one line, max 72 chars but prefer under 60, no period
- Name the essential change, not the mechanics or the file list
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
- Every note is one line under 90 characters; the summary is at most two short sentences
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

def pull_request (diff: str, commits: str, ticket: str = "") -> str:
   mark = f'- Start the title with the ticket: "{ticket} <title>"\n' if ticket else ""
   return f"""\
Write a pull request title and description for this change.

Return ONLY a JSON object: {{"title": "<title>", "body": "<markdown body>"}}

Rules:
- Title: one line, max 70 characters, imperative, no period
{mark}- Body: 1 to 5 markdown bullets, each ONE line under 90 characters
- Cover only what matters to a reviewer: behavior changes, contracts, risks
- Never enumerate every change; merge related work into one bullet
- State only what the commits and diff below actually contain; never invent
  features, flags, or command names
- No headings, no filler, no test plans, no attribution

Commits:
{commits}

Diff:
{diff}"""

def release_notes (subjects: str, tag: str) -> str:
   return f"""\
Condense these commit subjects into release notes for {tag}.

Rules:
- Output ONLY markdown bullets, each ONE line under 80 characters
- At most 6 bullets; merge related commits into one
- Keep only what a user of the tool would care about; drop chores,
  refactors, and internal churn unless they change behavior
- Every bullet must restate information present in the subjects below;
  NEVER invent features, flags, or command names that do not appear there
- Plain statements, no headings, no attribution

Commit subjects:
{subjects}"""

def verdict (name: str, age: str, diff: str) -> str:
   return f"""\
Judge one in-progress feature branch against trunk and return ONLY a JSON object:
{{"verdict": "integrate|discard|hold", "reason": "<one line under 80 characters>"}}

- integrate: the change is coherent, complete, and safe to land as-is
- discard: empty, abandoned, superseded, or plainly not worth keeping
- hold: incomplete, risky, or you are not confident; when in doubt, hold

Feature: {name} (age {age})

Diff against trunk (includes uncommitted work):
{diff}"""
