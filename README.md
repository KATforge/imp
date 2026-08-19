<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

<h1 align="center">Imp</h1>
<p align="center"><strong>Git-native workstreams for people and autonomous agents.</strong></p>

Imp isolates concurrent writers in worktrees, integrates exact candidates into trunk, and keeps every fact in Git itself.

## Install

```bash
pip install imp-git
imp doctor
```

## Workflow

```bash
imp start payment-retries --ticket SPK-12345
cd "$(imp worktree path payment-retries)"

imp commit
imp done

imp review     # AI-annotated diff of unpushed trunk; ask questions at the prompt
imp push
```

`imp start` creates one branch plus one worktree off fresh trunk. `--ticket` shapes the branch (`feature/SPK-12345-payment-retries`), and Imp warns when existing branches carry tickets and yours does not.

`imp commit` uses staged changes, or every dirty path when nothing is staged. It builds one commit off-ref and moves the branch only when it succeeds.

`imp done` builds the exact candidate, runs the project's checks against it in a throwaway worktree, shows the complete diff, integrates by compare-and-swap, and removes the branch and worktree. The move is stamped in trunk's reflog. `--all` integrates every open feature, oldest first, as one exact batch.

`imp undo` backs the most recent unpushed layer off trunk and restores it as a feature, so a failed trunk test costs one command.

`imp cleanup` judges every open feature with AI (integrate, discard, or hold), shows the verdict table for approval, and flattens the workspace. Discarded tips park under `refs/imp/attic` for 30 days. `--keep <name>` exempts a feature.

## Autonomy

Agents approve their own reversible work: `start`, `commit`, and `done` run without prompts for a detected agent session. Destructive and remote actions (`cleanup`, `undo`, `worktree remove`, `pr`, `release`) always need `--yes` or a person at the prompt. Humans are always asked. Preview anything with `--dry-run`.

## AI

`imp commit` sends the selected diff for a message (`-m` sends nothing). `imp review` sends the diff for annotations and answers. `imp cleanup` sends each feature's diff for a verdict. `imp doctor` only pings. `start`, `done`, `undo`, `status`, `pr`, and `release` are deterministic. Imp detects the actor automatically.

## State

Git is the database. A feature is its `feature/*` branch plus its worktree; age comes from the reflog, integration history from trunk's reflog, discarded work from `refs/imp/attic`. Multi-repository order and machine knobs live in Git configuration under `imp.*`. Imp writes no state files.

```bash
git config imp.worktrees ~/.worktrees    # managed worktree root (default)
git config imp.provider claude           # or ollama
git config --add imp.check "pytest -q"   # override check detection; "none" disables
```

Checks are otherwise detected from the project: a `package.json` test script, a `composer.json` test script, a pyproject mentioning pytest, or a Makefile `test:` target.

## Multiple repositories

```bash
imp start checkout --repo api --repo web
imp done checkout
```

Run these from the directory containing the repositories. The repeated `--repo` order is recorded as `imp.span.<name>.order` in each member and is the integration order.

## Automation

```bash
imp commit --json --dry-run
imp commit --json --yes
```

`--json` never prompts and emits one versioned envelope. `--dry-run` emits the exact ephemeral plan. `--yes` approves it.

## Git passthrough

Unknown commands run as Git with the same arguments and exit status.

```bash
imp diff --staged
imp log --oneline
imp push
```

Native commands are `cleanup`, `commit`, `doctor`, `done`, `pr`, `release`, `review`, `start`, `status`, `undo`, and `worktree`.

## Publishing

`imp pr` pushes the current branch and opens or updates its pull request. `--into develop` targets another branch instead of trunk.

`imp release` increments the patch version, tags the current clean commit, pushes, and publishes. Use an explicit version or `--major`, `--minor`, `--patch`, `--rc`, or `--stable`. `--local` only creates the tag.

See the [documentation](https://docs.katforge.com/packages/imp/) and [JSON protocol](https://docs.katforge.com/packages/imp/json-protocol).

## License

[MIT](LICENSE)
