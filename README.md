<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

<h1 align="center">Imp</h1>
<p align="center"><strong>Git-native workstreams for people and autonomous agents.</strong></p>

Imp puts every change on trunk as one exact, reviewed, undoable layer — whether a person typed it or an agent shipped it. Concurrent writers never collide, nothing is ever lost, and Git itself is the only database.

## Install

```bash
pip install imp-git
imp doctor
```

## The loop

```bash
imp start payment-retries      # trunk free → work in place; busy → isolated worktree
imp commit                     # one exact commit, message written from the diff
imp done                       # land it: checks, full diff, compare-and-swap
imp review                     # annotated diff of unpushed trunk; ask it questions
imp push
```

`imp start` is trunk-first. When the trunk lock is free and the checkout is clean, work happens directly in the current checkout — live for whatever runs from trunk — and the session becomes one layer. When trunk is busy, imp creates a branch plus worktree off fresh trunk instead, so concurrent agents cascade: the first takes trunk, the rest take worktrees, nobody names a mode. `--worktree` forces isolation; `--ticket SPK-12345` carries a ticket into branch names and commit subjects.

`imp commit` builds the commit off-ref from staged changes (or every dirty path) and only moves the branch when it succeeds. On trunk it claims or renews the lock automatically.

`imp done` integrates exactly what it showed you: the candidate is rebased or merged off-ref, the project's checks run against it in a throwaway worktree, and trunk moves by compare-and-swap. For a trunk session it releases the lock. Either way the work is recorded as one layer. `--all` lands every open feature, oldest first.

## The net

```bash
imp undo        # lift the newest layer off trunk, restore it as a feature worktree
imp cleanup     # AI judges every open feature: integrate, discard, or hold
```

`imp undo` unwinds layers newest-first: trunk steps back, the work comes back as `feature/<name>` with its worktree, ready to fix and land again. A live trunk session undoes midway. Pushed layers refuse — revert those.

`imp cleanup` flattens the workspace. Each open feature's full difference against trunk, uncommitted work included, gets an AI verdict shown for approval. Integrations run the checks and land dependency-first; discards park under `refs/imp/attic` for 30 days; holds stay put, because flat with exceptions beats flat at all costs.

## State

Git is the database. A feature is its branch plus its worktree. Layers live in `refs/imp/layer`, locks in `refs/imp/lock` (moved by compare-and-swap, so racing acquirers get exactly one winner), discarded work in `refs/imp/attic`, history in the reflog. Span order and knobs are Git configuration:

```bash
git config imp.worktrees ~/.worktrees     # managed worktree root (default)
git config imp.provider claude            # or ollama
git config --add imp.check "pytest -q"    # override check detection; "none" disables
```

Checks are otherwise detected from the project: an npm or composer test script, a pyproject with pytest, a Makefile test target. Imp writes no state files, so there is nothing to migrate, repair, or trust.

## Many repositories

```bash
imp start checkout --repo api --repo web
imp done checkout
```

Run from the directory holding the checkouts: it is the workspace, no manifest required. The `--repo` order is the dependency order — recorded in each member, replayed at integration, refused as a whole if any member is blocked.

## Agents

Agents run the same commands. They approve their own reversible work — `start`, `commit`, and `done` never stall on a prompt — while destructive and remote actions (`undo`, `cleanup`, `worktree remove`, `pr`, `release`) always need `--yes` or a person. `--json` gives every command a versioned envelope and never prompts; `--dry-run` shows the exact plan and changes nothing.

`imp commit` and `imp pr` send their diffs to AI (`-m` sends nothing); `imp review` and `imp cleanup` send diffs for annotations and verdicts; `imp release` condenses commit subjects into notes. Everything generated is terse — one-line subjects, essentials-only bullets — and never carries AI attribution.

## Publishing

`imp pr` pushes the branch and opens or updates its pull request — AI-written title and description, shown for approval first. `--into develop` targets another base; `-m "title"` stays deterministic.

`imp release` tags a SemVer release from the clean current commit and publishes it to GitHub with condensed notes. Pass a version, or `--major`, `--minor`, `--patch`, `--rc`, `--stable`; `--local` only tags.

Everything else — `imp push`, `imp log`, `imp diff` — is Git, passed through untouched.

See the [documentation](https://docs.katforge.com/packages/imp/) and [JSON protocol](https://docs.katforge.com/packages/imp/json-protocol).

## License

[MIT](LICENSE)
