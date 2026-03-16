# imp

AI-powered git workflow. Commit, branch, review, and release without writing commit messages, branch names, or PR descriptions.

```bash
imp commit -a        # stages everything, generates message, commits
imp branch "auth"    # creates feat/user-auth
imp review           # AI code review of your changes
imp release          # squash, changelog, tag, push
```

Every command works with or without a network connection (swap Claude for a local Ollama model). No config files, no lock-in: a Python CLI that wraps git.

## Install

```bash
git clone https://github.com/anders458/imp.git
cd imp
pip install -e .
imp doctor    # verify setup
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install -e .
```

## Commands

### Daily workflow

```
imp commit [-a]    Generate commit message from diff (-a to stage all)
imp amend          Rewrite last commit message
imp undo [N]       Undo last N commits, keep changes staged
imp revert         Safely undo a pushed commit
imp sync           Pull, rebase, push in one step
```

### Branching

```
imp branch <desc>  Create branch from plain English description
imp fix <issue>    Create branch from GitHub issue number
imp pr             Create pull request with AI title and body
imp done           Clean up after PR merge
```

### Analysis

```
imp review         AI code review of staged or unstaged changes
imp split          Group dirty files into logical commits via AI
imp status         Repo overview: branch, changes, commits
imp log [-n N]     Pretty commit graph
```

### Release

```
imp release        Squash commits, generate changelog, tag, push
```

### Utilities

```
imp clean          Delete merged branches
imp doctor         Verify tools (git, claude, ollama, gh)
imp help           Show workflow guide
```

## Examples

```bash
# Commit with zero effort
git add .
imp commit
# -> "Add rate limiting to API endpoints"
# -> Use this message? [Y/n/e]

# Stage everything and commit in one shot
imp commit -a

# Branch from a description
imp branch "add user authentication"
# -> Suggested: feat/user-auth
# -> Create branch? [Y/n]

# Branch from a GitHub issue
imp fix 42
# -> Fetches issue, suggests fix/login-redirect-42

# Ship a release
imp release
# -> Version bump: patch/minor/major
# -> Generates changelog, squashes, tags, pushes
```

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

```bash
export IMP_AI_PROVIDER=claude     # claude (default) or ollama
export IMP_AI_MODEL_FAST=haiku    # quick tasks: commit, branch
export IMP_AI_MODEL_SMART=sonnet  # complex tasks: review, PR, release
```

For fully local AI with Ollama:

```bash
export IMP_AI_PROVIDER=ollama
export IMP_AI_MODEL_FAST=llama3.2
export IMP_AI_MODEL_SMART=llama3.2
```

## Requirements

- Python 3.10+
- git
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or [Ollama](https://ollama.com)
- [gh](https://cli.github.com) (optional: `imp fix`, `imp pr`, `imp release`)

## License

MIT
