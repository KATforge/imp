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

## Why

AI agents can run git for you, but they improvise every time. Imp is opinionated: same format, same workflow, same result, every time.

- **Consistent commits** across your whole team, validated against [Conventional Commits](https://www.conventionalcommits.org/) before anything touches git
- **One-command releases** that squash, changelog, tag, and push with automatic rollback on failure
- **Fast and deterministic.** One command, not a conversation. No reasoning, no retries, no surprises.
- **AI writes the words, Imp controls the workflow.** What gets staged, how it's validated, when it's safe to push.
- **Works offline** with local models via Ollama. No API key required.

## Install

```bash
uv tool install git+https://github.com/anders458/imp.git
```

Or with pip:

```bash
pip install git+https://github.com/anders458/imp.git
```

Then set up your AI provider and verify:

```bash
imp config
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
| `imp push` | Push commits to origin. Sets upstream on first push. |
| `imp sync` | Pull, rebase, push in one step. |
| `imp resolve` | AI-assisted merge conflict resolution. |

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

### Setup

| Command | Description |
|---|---|
| `imp config` | Interactive AI provider and model setup. |
| `imp doctor` | Verify tools, config, and AI connection. |
| `imp clean` | Delete merged branches (local and remote). |
| `imp help` | Show workflow guide and commit format reference. |

Any AI command accepts `--whisper` / `-w` to hint the AI without overriding its rules:

```bash
imp commit -a -w "use IMP-42 as ticket"
imp review -w "focus on error handling"
```

## Workflows

| Flow | Steps |
|---|---|
| **Solo** | `commit -a` → `push` → `release` |
| **Feature branch** | `branch` → `commit -a` → `pr` → `done` |
| **Hotfix** | `fix 42` → `commit -a` → `pr` → `done` |
| **Merge conflict** | `sync` or `done` → `resolve` → continue |

## Commit Format

Imp generates [Conventional Commits](https://www.conventionalcommits.org/) messages, validated before use.

```
type: message              feat, fix, refactor, build, chore,
type(scope): message       docs, test, style, perf, ci
type!: message             (breaking change)
```

All lowercase after the colon (except ticket IDs). Imperative mood. Max 72 chars, no period. Tickets after the colon: `fix: IMP-42 resolve timeout`. Scopes optional: `refactor(auth): simplify flow`.

## Configuration

```bash
imp config
```

Interactive menu to set your AI provider and models. Stored in `~/.config/imp/config.json`.

| Setting | Default | Description |
|---|---|---|
| `provider` | `claude` | AI provider: `claude` or `ollama` |
| `model:fast` | `haiku` | Model for quick tasks (commit, branch) |
| `model:smart` | `sonnet` | Model for complex tasks (review, PR, split) |

Environment variables (`IMP_AI_PROVIDER`, `IMP_AI_MODEL_FAST`, `IMP_AI_MODEL_SMART`) override the config file when set, useful for CI.

## Requirements

- Python 3.10+
- git
- [gh](https://cli.github.com) (optional, for `imp fix`, `imp pr`, `imp release`)

### Claude Code (default)

Imp uses [Claude Code](https://docs.anthropic.com/en/docs/claude-code) as its default AI provider. You need an active Claude Code subscription.

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude          # authenticate
imp doctor      # verify
```

### Ollama (local, free)

For fully offline usage with no API key:

```bash
# Install from https://ollama.com, then:
ollama pull llama3.2
imp config      # select ollama and your models
imp doctor      # verify
```

## Development

```bash
git clone https://github.com/anders458/imp.git
cd imp
pip install -e ".[dev]"
pytest -v
ruff check src/ tests/
```

## License

[MIT](LICENSE)
