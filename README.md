<p align="center">
   <img src="logo.png" alt="imp" width="200">
</p>

<p align="center">
   AI-powered git workflow.<br>
   Commit, branch, review, and release without writing commit messages, branch names, or PR descriptions.
</p>

<p align="center">
   <a href="#install">Install</a> &middot;
   <a href="#quick-start">Quick Start</a> &middot;
   <a href="#commands">Commands</a> &middot;
   <a href="#commit-format">Commit Format</a> &middot;
   <a href="#configuration">Configuration</a> &middot;
   <a href="#license">License</a>
</p>

---

```bash
imp commit -a        # stages everything, generates message, commits
imp branch "auth"    # creates feat/user-auth
imp review           # AI code review of your changes
imp release          # squash, changelog, tag, push
```

Every command works with or without a network connection (swap Claude for a local Ollama model). No config files, no lock-in: a Python CLI that wraps git.

## Why

AI agents can run git for you, but they improvise every time. Imp is opinionated: same format, same workflow, same result, every time.

- **Consistent commits** across your whole team, validated against [Conventional Commits](https://www.conventionalcommits.org/) before anything touches git
- **One-command releases** that squash, changelog, tag, and push with automatic rollback on failure
- **Fast and deterministic.** One command, not a conversation. No reasoning, no retries, no surprises.
- **AI writes the words, Imp controls the workflow.** What gets staged, how it's validated, when it's safe to push.
- **Works offline** with local models via Ollama. No API key required.

## Table of Contents

- [Why](#why)
- [Install](#install)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [Daily Workflow](#daily-workflow)
  - [Branching](#branching)
  - [Analysis](#analysis)
  - [Release](#release)
  - [Utilities](#utilities)
- [AI Whisper](#ai-whisper)
- [Commit Format](#commit-format)
- [Workflows](#workflows)
- [Configuration](#configuration)
- [Requirements](#requirements)
- [Development](#development)
- [License](#license)

## Install

```bash
pip install imp-git
```

Or from source:

```bash
git clone https://github.com/anders458/imp.git
cd imp
pip install -e .
```

Verify your setup:

```bash
imp doctor
```

## Quick Start

```bash
# Make some changes, then commit with an AI message
imp commit -a
# -> "feat: add rate limiting to API endpoints"
# -> Use this message? [Yes / Edit / No]

# Branch from a description
imp branch "add user authentication"
# -> Suggested: feat/user-auth
# -> Create branch? [Yes / No]

# Branch from a GitHub issue
imp fix 42
# -> Fetches issue, suggests fix/login-redirect-42

# Ship a release
imp release
# -> Version bump: patch / minor / major
# -> Generates changelog, squashes, tags, pushes
```

## Commands

### Daily Workflow

| Command | Description |
|---|---|
| `imp commit [-a]` | Generate commit message from diff. `-a` stages all. |
| `imp amend` | Rewrite last commit message from the full diff. |
| `imp undo [N]` | Undo last N commits, keep changes staged. |
| `imp revert [hash]` | Safely revert a pushed commit. |
| `imp sync` | Pull, rebase, push in one step. |

### Branching

| Command | Description |
|---|---|
| `imp branch <desc>` | Create branch from plain English description. |
| `imp branch` | Interactive branch switcher. |
| `imp fix <issue>` | Create branch from GitHub issue number. |
| `imp pr` | Create pull request with AI title and body. |
| `imp done [target]` | Merge feature branch, clean up local and remote. |

### Analysis

| Command | Description |
|---|---|
| `imp review` | AI code review of staged or unstaged changes. |
| `imp split` | Group dirty files into logical commits via AI. |
| `imp status` | Repo overview: branch, changes, sync state. |
| `imp log [-n N]` | Pretty commit graph. |

### Release

| Command | Description |
|---|---|
| `imp release` | Squash commits, generate changelog, tag, push, create GitHub release. |
| `imp ship [level]` | Commit all + release in one shot, no prompts. Default: patch. |

### Utilities

| Command | Description |
|---|---|
| `imp clean` | Delete merged branches (local and remote). |
| `imp doctor` | Verify tools: git, claude, ollama, gh. |
| `imp help` | Show workflow guide and commit format reference. |

## AI Whisper

Every AI command accepts `--whisper` / `-w` to give the AI a hint without overriding its rules:

```bash
imp commit -a -w "use IMP-99999 as ticket"
imp branch "auth flow" -w "use feat/ prefix"
imp review -w "focus on error handling"
imp pr -w "mention the database migration"
```

The hint is injected as context before the AI's format rules, so the output still conforms to Conventional Commits, length limits, etc.

## Commit Format

imp generates [Conventional Commits](https://www.conventionalcommits.org/) messages. All commit messages are validated before use.

**Format:**

```
type: message
type(scope): message
type!: message              # breaking change
```

**Types:**

| Type | Purpose | Type | Purpose |
|---|---|---|---|
| `feat` | New feature | `build` | Build system, deps |
| `fix` | Bug fix | `chore` | Maintenance, config |
| `refactor` | Restructure code | `docs` | Documentation |
| `test` | Add/update tests | `style` | Formatting, whitespace |
| `perf` | Performance | `ci` | CI/CD pipelines |

**Rules:**

- All lowercase after the colon (except ticket IDs like `IMP-123`)
- Imperative mood: "add" not "added", "fix" not "fixes"
- Max 72 characters, no period at the end
- Tickets go after the colon: `fix: IMP-123 resolve timeout`
- Scopes are optional: `refactor(auth): simplify flow`

## Workflows

**Solo (trunk-based):**

```
imp commit -a  ->  imp commit -a  ->  imp release
```

**Feature branch:**

```
imp branch  ->  imp commit -a  ->  imp pr  ->  imp done
```

**Hotfix:**

```
imp fix 42  ->  imp commit -a  ->  imp pr  ->  imp done
```

## Configuration

imp uses environment variables. No config files needed.

| Variable | Default | Description |
|---|---|---|
| `IMP_AI_PROVIDER` | `claude` | AI provider: `claude` or `ollama` |
| `IMP_AI_MODEL_FAST` | `haiku` | Model for quick tasks (commit, branch) |
| `IMP_AI_MODEL_SMART` | `sonnet` | Model for complex tasks (review, PR, split) |

**Fully local with Ollama:**

```bash
export IMP_AI_PROVIDER=ollama
export IMP_AI_MODEL_FAST=llama3.2
export IMP_AI_MODEL_SMART=llama3.2
```

## Requirements

- Python 3.10+
- git
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or [Ollama](https://ollama.com)
- [gh](https://cli.github.com) (optional, for `imp fix`, `imp pr`, `imp release`)

## Development

```bash
git clone https://github.com/anders458/imp.git
cd imp
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint
ruff check src/ tests/
```

## License

[MIT](LICENSE)
