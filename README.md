<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

<h1 align="center">Imp</h1>
<p align="center"><strong>Safe Git workstreams for people and parallel AI agents.</strong></p>

Imp prevents concurrent work from sharing one writable checkout or becoming one enormous final commit.

It creates isolated Git worktrees, records one writer per workstream, plans logical Conventional Commits, and lets local tools switch between active source trees.

Generated work never credits an AI agent, model, or provider. Resolved actor IDs stay in local workflow state and machine output.

## Install

```bash
pip install imp-git
imp config
imp doctor
```

Install the user-level agent adapters with `python adapters/install.py`.
Codex requires one explicit `/hooks` review after each new or changed hook installation.
Confirm effective enforcement with `imp doctor --agents`.

## Managed workflow

```bash
imp start payment-retries --task "Improve failed-payment recovery"
cd "$(imp worktree path payment-retries)"

# Edit and test in the isolated worktree.
imp commit --plan
imp commit --apply --yes

imp done --plan
imp review
imp done --apply --yes

imp use
imp active --path
```

Omitting an existing feature opens a picker. Review asks whether to mark the exact candidate after displaying it.

`imp start` branches from freshly verified remote trunk by default.

The plan creates no branch or worktree. Apply revalidates the exact base before changing Git state.

`imp commit` plans staged changes, or all dirty changes when nothing is staged. It can split separate hunks from the same file into different commits. Apply builds the complete commit chain off-ref and moves the branch only after every commit succeeds.

`imp split` is the exact alias for `imp commit --all`.

## Direct adoption

A managed worktree is optional unless repository policy sets `feature:required`.

```bash
imp commit -m "fix(auth): preserve the refresh token"
imp commit
imp split
imp review
```

Manual `-m` commits do not use AI or add another confirmation.

## Parallel agents

Give every concurrent writer a separate feature:

```bash
IMP_ACTOR_ID=actor:codex:payments imp start payments --yes
IMP_ACTOR_ID=actor:claude:profile imp start profile --yes
```

Imp stores feature records, plans, claims, and active selection under the repository's common Git directory. Nothing is written to project-level agent instruction files.

Agents normally receive `IMP_ACTOR_ID` from their user-level adapter. Humans do not need to type it.

Outside Git, the adapter allows ordinary file edits without initializing Git or Imp.

## Automation

```bash
imp --json --no-input commit --plan
imp --json --no-input commit --apply plan:commit:payments:1 --yes
imp active --path
imp context payment-retries --json
```

Persisted JSON and command results declare independent schemas. Saved plans bind exact Git and file fingerprints and become stale when their inputs change. See the [JSON protocol](docs/json-protocol.md).

## Git passthrough

Imp owns only its workflow commands. Everything else runs as ordinary Git with unchanged arguments and exit status.

```bash
imp diff --staged
imp log --oneline
imp push
imp restore src/auth.py
```

Native commands are `start`, `use`, `status`, `done`, `commit`, `review`, `resolve`, `changelog`, `ship`, `init`, `config`, `doctor`, `active`, `context`, `worktree`, `recover`, and the `split` compatibility alias.

## Repository policy

Committed policy lives in `.imp`:

```json
{
   "schema": "imp.config.v1",
   "feature:required": false,
   "worktree:setup": [
      { "name": "dependencies", "run": ["uv", "sync"] }
   ],
   "worktree:share": [".env.local"]
}
```

Setup commands are argv arrays. Shared paths must be explicitly allowed, ignored, untracked, and inside the primary repository.

See the [Imp documentation](https://docs.katforge.com/packages/imp/) for the complete workflow.

## License

[MIT](LICENSE)
