# Contributing

```bash
pip install -e ".[dev]"
uv run ruff check .
uv run pytest
```

Use 3-space indentation, spaces inside brackets, snake_case data fields, Conventional Commits, and the narrow Git boundary in `git.py`. Do not run Ruff's formatter.

Open pull requests against `master` with `imp pr`.
