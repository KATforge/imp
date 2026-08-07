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
pytest        # full suite
pytest tests/test_release.py -v
```

## Lint

```bash
ruff check src tests
ruff format --check src tests   # style is intentionally non-PEP8, see pyproject.toml
```

The formatter is **not** auto-run. Style rules in `pyproject.toml` reflect deliberate divergence (3-space indent, spaces inside brackets, `match` over `elif`). Don't reformat existing code on a whim.

## Project shape

```
src/imp_git/
   ai.py          # provider dispatch (claude CLI, ollama HTTP)
   git.py         # subprocess wrapper, one fluent function per git verb
   prompts.py     # all AI prompts in one place (SSOT)
   config.py      # ~/.config/imp/config.json + env overrides
   console.py     # rich-based output, spinner, prompts
   workflow.py    # shared command primitives (review_commit)
   commands/      # one file per `imp <command>`
```

## Conventions

- Conventional Commits enforced by `imp commit` and the validator
- One word per fluent segment (`git.diff()`, not `git.getDiff()`)
- Snake_case for response/config fields
- Add a test for any bug fix; integration tests preferred over mocks for git operations

## PR

Open a PR against `master`. `imp pr` works for this.
