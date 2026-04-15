# Demo GIFs

Reproducible GIFs for the project README, rendered with [VHS](https://github.com/charmbracelet/vhs) in Docker. No AI keys needed: a stub `claude` binary returns canned responses so the demos are deterministic.

## Render

From the repo root:

```bash
./demo/run.sh
```

This builds `imp-demo:latest` and renders `tidy.gif`, `commit.gif`, `pr.gif` into `demo/`.

## Layout

- `Dockerfile` — extends `ghcr.io/charmbracelet/vhs`, installs `imp` and the stubs
- `fake-claude`, `fake-gh` — stub binaries on PATH in place of the real CLIs
- `setup-tidy.sh`, `setup-commit.sh`, `setup-pr.sh` — build fresh demo repos in `/tmp/demo-repo`
- `*.tape` — VHS scripts driving each demo
- `run.sh` — one-shot: build + render all tapes

## Tweak a demo

1. Edit the tape file (timing, theme, commands).
2. Edit the matching setup script if you need different starting state.
3. Re-run `./demo/run.sh` (or `docker run --rm -v "$PWD/demo:/vhs" imp-demo <file>.tape` for a single tape).

Tape reference: https://github.com/charmbracelet/vhs#vhs-command-reference
