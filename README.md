<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

# Imp — AI git CLI for commit messages, history, changelogs, and PRs

[![PyPI](https://img.shields.io/pypi/v/imp-git.svg)](https://pypi.org/project/imp-git/)
[![Python](https://img.shields.io/pypi/pyversions/imp-git.svg)](https://pypi.org/project/imp-git/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`imp` is a git CLI that uses AI for the parts git leaves to you: commit messages, splitting dirty working trees into logical commits, rewriting past history, generating changelogs, opening pull requests, and resolving merge conflicts. It runs against the Claude CLI or a local Ollama model.

Comparable to [aicommits](https://github.com/Nutlope/aicommits) and [OpenCommit](https://github.com/di-sukharev/opencommit), but covers the whole workflow rather than only the commit message.

---

## Demo

![imp tidy](demo/tidy.gif)

---

## Example

Before:

```
$ git status
 M src/auth.py
 M src/api.py
 M tests/test_auth.py
 M README.md
?? src/rate_limit.py
```

Run:

```bash
imp split
```

After:

```
$ git log --oneline
a1b2c3d  feat(auth): add rate limiting to login
e4f5g6h  test(auth): cover rate-limit edge cases
i7j8k9l  docs: document new auth flags
```

One dirty tree, three coherent Conventional Commits.

---

## Install

```bash
pip install imp-git
# or, no install at all:
uvx --from imp-git imp doctor
pipx run --spec imp-git imp doctor
```

Configure your AI provider:

```bash
imp config
imp doctor
```

Works with the Claude CLI or local Ollama models. No API key required for Ollama.

---

## Usage

```bash
imp split           # group dirty files into logical commits
imp commit -a       # stage everything, generate a commit message
imp pr              # open a PR with AI title and body
imp release         # squash, changelog, tag, push
imp fleet ~/code    # ship every dirty repo in a directory
```

---

## More Examples

### Commit

![imp commit](demo/commit.gif)

```bash
$ imp commit -a
→ feat: add rate limiting to API endpoints
  Use this message? [Yes / Edit / No]
```

### PR

![imp pr](demo/pr.gif)

```bash
$ imp pr
→ Title: feat: rate limit auth endpoints
→ Body:  ## Summary
         Adds per-IP rate limiting to /login and /register...
  Create PR? [Yes / Edit / No]
```

### Release

![imp release](demo/release.gif)

```bash
$ imp release
→ Bump: patch / minor / major
→ Squashes commits, writes CHANGELOG.md, tags v0.0.1, pushes.
```

Skip the chooser with `--patch`, `--minor`, or `--major`. Add `--rc` for a release candidate, `--stable` to promote one.

### Fleet

```bash
$ imp fleet ~/Projects --patch --stable
→ Scans for every git repo under ~/Projects
→ Runs imp ship on each dirty one
→ Prints a summary at the end
```

Flags apply to every repo; omit them to be prompted per-repo.

---

## Why imp

- Commit messages, PR titles, PR bodies, and changelog entries are generated from the diff.
- [Conventional Commits](https://www.conventionalcommits.org/) are validated before any commit lands.
- A dirty working tree can be grouped into multiple logical commits in one step.
- Merge conflicts can be resolved with AI assistance, with review prompts for each file.
- `imp release` handles squash, changelog, tag, and push as one operation.

---

## How `imp` compares

| | imp | aicommits | OpenCommit | commitizen |
|---|---|---|---|---|
| Commit message from diff | yes | yes | yes | prompts you |
| Conventional Commits | enforced | optional | optional | enforced |
| Split dirty tree into commits | yes | — | — | — |
| Rewrite past history | yes (`tidy`) | — | — | — |
| AI changelog | yes | — | — | template |
| AI PR title + body | yes | — | — | — |
| AI merge conflict resolution | yes | — | — | — |
| Local models (Ollama) | yes | partial | yes | n/a |
| Claude CLI | yes | — | — | n/a |
| Runtime deps | 3 | many (Node) | many (Node) | many (Python) |

`aicommits` and `OpenCommit` cover the commit-message step. `imp` covers the whole loop: dirty tree → clean commits → PR → release → changelog.

---

## When to use imp

- A dirty working tree with unrelated edits that should be separate commits.
- A release to cut, with changelog and tag.
- A PR to open where the diff mostly explains itself.
- A merge conflict where a second pair of eyes would help.
- A past commit or range that needs to be rewritten into something cleaner.

---

## Commands

| Command | Purpose |
|---|---|
| `imp commit [-a] [-p] [-y] [-E glob] [-w hint]` | Generate commit message from diff |
| `imp amend [-y] [-p] [-w hint]` | Fold uncommitted changes into last commit, regenerate message, optionally force-push |
| `imp split [-y] [-w hint]` | Group dirty files into logical commits |
| `imp tidy [range] [-y] [-w hint]` | Rewrite past history: reword, squash, drop. Range = count, ref, `a..b`, or `"1 year ago"` |
| `imp undo [N]` | Undo last N commits, keep changes |
| `imp revert [hash] [-y] [-w hint]` | Safely revert a commit |
| `imp push [-w hint]` | Push, sets upstream on first push |
| `imp sync [-y]` | Pull, rebase, push |
| `imp resolve [--ours] [--theirs] [-y] [-w hint]` | AI-assisted conflict resolution |
| `imp branch <desc> [-y] [-w hint]` | Create branch from description |
| `imp fix <issue> [-y] [-w hint]` | Create branch from GitHub issue |
| `imp pr [-y] [-w hint]` | Open PR with AI title and body |
| `imp done [target] [-y]` | Merge branch, clean up local and remote |
| `imp review [-l N] [-f] [-d] [-w hint]` | AI code review |
| `imp changelog [--since tag] [--apply] [-y]` | Regenerate CHANGELOG.md |
| `imp status` | Repo overview |
| `imp log [-n N] [ref]` | Pretty commit graph |
| `imp release [--patch\|--minor\|--major] [--rc\|--stable]` | Squash, changelog, tag, push |
| `imp ship [--patch\|--minor\|--major] [--rc\|--stable] [--squash] [-w hint]` | Split, then release. `--squash` collapses into one release commit |
| `imp fleet [path] [--patch\|--minor\|--major] [--rc\|--stable] [--squash] [-d N] [--dry-run]` | Ship every dirty repo in a directory |
| `imp setup <url>` | Init repo, remote, `.gitignore` |
| `imp config` | Configure AI provider |
| `imp doctor` | Verify install and config |
| `imp clean` | Delete merged branches |

Any AI command accepts `-w` / `--whisper` to steer the AI without overriding its rules:

```bash
imp commit -a -w "use IMP-42 as ticket"
imp review -w "focus on error handling"
```

---

## Configuration

`imp config` writes `~/.config/imp/config.json` (or `$XDG_CONFIG_HOME/imp/config.json`).

```json
{
   "provider": "claude",
   "model:fast": "haiku",
   "model:smart": "sonnet"
}
```

| Key | Purpose | Values |
|---|---|---|
| `provider` | AI backend | `claude`, `ollama` |
| `model:fast` | Short prompts (commit messages, dates) | Any model name your provider knows |
| `model:smart` | Reasoning prompts (split, tidy, resolve, review) | Any model name your provider knows |

Each key has a matching env var (`IMP_AI_PROVIDER`, `IMP_AI_MODEL_FAST`, `IMP_AI_MODEL_SMART`) that wins over the file.

---

## Requirements

- Python 3.10+
- git
- [gh](https://cli.github.com) (optional, for `fix`, `pr`, `release`)
- An AI backend: the [Claude CLI](https://docs.claude.com/en/docs/claude-code) **or** a running [Ollama](https://ollama.com) instance

---

## License

[MIT](LICENSE)
