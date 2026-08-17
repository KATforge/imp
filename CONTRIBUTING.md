# Contributing to imp

## Setup

```bash
imp clone https://github.com/<you>/imp.git
cd imp
pip install -e ".[dev]"
```

## Run

```bash
imp doctor    # verify install + AI connection
```

## Test

```bash
uv run pytest
uv run pytest tests/test_integration.py -v
```

## Lint

```bash
uv run ruff check .
```

The project intentionally uses 3-space indentation and spaces inside brackets. Do not run Ruff's formatter.

## Project shape

```
src/imp_git/
   commands/        # CLI boundary
   features.py      # worktrees and claims
   commit_plan.py   # exact logical commit plans
   integration.py   # review and completion candidates
   source_release.py # exact source releases
   plans.py         # immutable plan records
   state.py         # common-directory state and locks
   git.py           # narrow Git subprocess boundary
```

## Conventions

- Conventional Commits enforced by `imp commit` and the validator
- Keep the Git boundary narrow (`git.diff()`, not `git.getDiff()`)
- Snake_case for response/config fields
- Add a test for any bug fix; integration tests preferred over mocks for git operations

## PR

Open a PR against `master`. `imp done --pr` works for a managed feature.
