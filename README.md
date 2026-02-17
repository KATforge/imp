# imp

AI-powered git toolkit. Small shell scripts, pluggable AI backend, zero dependencies beyond bash and git.

## Install

```bash
git clone https://github.com/yourusername/imp.git
cd imp
./install.sh
source ~/.bashrc
```

Verify setup:

```bash
imp doctor
```

## Commands

### Daily workflow

```
imp commit      Generate commit message from staged changes (-a to stage all)
imp amend       Amend last commit with new AI message
imp undo [N]    Undo last N commits (keeps changes staged)
imp revert      Safely undo a pushed commit
imp stash       Stash changes with AI message (also: list, pop)
imp sync        Pull, rebase, push
```

### Branching

```
imp branch      Create branch from description
imp fix         Create branch from GitHub issue
imp pr          Create pull request with AI title and description
```

### Analysis

```
imp diff        Explain changes in plain English
imp review      AI code review of staged or unstaged changes
imp describe    Explain what a branch does
imp list        Show repo overview (branch, changes, commits)
```

### Release

```
imp release     Squash commits, generate changelog, tag, and push
imp init        Initialize new repository with AI-generated .gitignore
```

### Help

```
imp help        Show workflow guide with example flows
imp doctor      Check dependencies and configuration
imp --version   Show version
```

## Examples

```bash
# Quick commit
git add .
imp commit
# → "Add rate limiting to API endpoints"
# → Use this message? [Y/n/e]

# Stage everything and commit
imp commit -a

# Create a feature branch
imp branch "add user authentication"
# → Suggested: feat/user-auth
# → Create branch? [Y/n]

# Fix a GitHub issue
imp fix 42
# → Fetches issue, suggests fix/login-redirect-42

# Ship a release
imp release
# → Shows commits since last tag
# → Version bump: patch/minor/major
# → Generates changelog
# → Squashes, tags, pushes
```

## Workflows

**Solo (trunk-based):**

```
imp commit -a  →  imp commit -a  →  imp release
```

**Feature branch:**

```
imp branch  →  imp commit -a  →  imp pr
```

**Hotfix:**

```
imp fix 42  →  imp commit -a  →  imp pr
```

## Configuration

Environment variables:

```bash
export IMP_AI_PROVIDER=claude     # claude or ollama
export IMP_AI_MODEL_FAST=haiku    # quick tasks (commit, branch, stash)
export IMP_AI_MODEL_SMART=sonnet  # complex tasks (review, PR, release)
```

For Ollama:

```bash
export IMP_AI_PROVIDER=ollama
export IMP_AI_MODEL_FAST=llama3.2
export IMP_AI_MODEL_SMART=llama3.2
```

## Structure

```
imp/
├── bin/
│   ├── imp              # dispatcher
│   ├── imp-amend
│   ├── imp-branch
│   ├── imp-commit
│   ├── imp-describe
│   ├── imp-diff
│   ├── imp-doctor
│   ├── imp-fix
│   ├── imp-help
│   ├── imp-init
│   ├── imp-list
│   ├── imp-pr
│   ├── imp-release
│   ├── imp-revert
│   ├── imp-review
│   ├── imp-stash
│   ├── imp-sync
│   └── imp-undo
├── lib/
│   ├── ai.sh            # pluggable AI interface
│   ├── common.sh        # shared helpers
│   └── prompts.sh       # AI prompt templates
├── tests/
│   ├── helpers.bash     # test utilities
│   ├── common.bats      # unit tests
│   └── commands.bats    # integration tests
├── install.sh
├── LICENSE
├── CHANGELOG.md
└── README.md
```

## Requirements

- bash
- git
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or [Ollama](https://ollama.com)
- [gh](https://cli.github.com) (optional, for `imp fix` and `imp pr`)
- [jq](https://jqlang.github.io/jq/download) (optional, for Ollama provider and `imp fix`)
- [glow](https://github.com/charmbracelet/glow) (optional, for rich markdown rendering)

## License

MIT
