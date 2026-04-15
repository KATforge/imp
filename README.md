<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

# Imp: clean up your git history with AI

Messy commits, vague messages, and sloppy PRs slow teams down.
`imp` rewrites a dirty working tree into clean, Conventional Commits and ships them with a real changelog. One command, every time.

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
imp split       # group dirty files into logical commits
imp commit -a   # stage everything, generate a commit message
imp pr          # open a PR with AI title and body
imp release     # squash, changelog, tag, push
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

Add `--rc` for a release candidate, `--stable` to promote one.

---

## Why not just use git?

- `git` doesn't write commit messages. You do. Badly, at 2am.
- `git` doesn't group changes. You end up with `wip`, `fix stuff`, `more fixes`.
- `git` doesn't validate commits. `imp` enforces [Conventional Commits](https://www.conventionalcommits.org/) before anything lands.
- `git` doesn't know what changed. `imp` reads the diff and writes the message.

---

## When to use imp

- You have a pile of unrelated edits and need clean, reviewable commits
- You're about to push `wip: stuff` and know it
- You're cutting a release and don't want to handwrite a changelog
- You're opening a PR and the diff speaks for itself
- You're resolving a merge conflict and want a second pair of eyes

---

## Commands

| Command | Purpose |
|---|---|
| `imp commit [-a] [-p] [-y] [-E glob] [-w hint]` | Generate commit message from diff |
| `imp amend [-y] [-w hint]` | Rewrite last commit message |
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
| `imp release [--rc] [--stable]` | Squash, changelog, tag, push |
| `imp ship [level] [--rc] [--stable] [-w hint]` | Split, then release |
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

## Requirements

- Python 3.10+
- git
- [gh](https://cli.github.com) (optional, for `fix`, `pr`, `release`)

---

## License

[MIT](LICENSE)
