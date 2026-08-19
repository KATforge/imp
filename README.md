<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

<h1 align="center">Imp</h1>
<p align="center"><strong>Safe Git worktrees and exact local commits.</strong></p>

Imp isolates concurrent writers, plans exact changes, and integrates one feature at a time.

## Install

```bash
pip install imp-git
imp doctor
```

## Workflow

```bash
imp start payment-retries
cd "$(imp worktree path payment-retries)"

imp commit
imp done
```

`imp commit` uses staged changes, or every dirty path when nothing is staged. It builds one commit off-ref and moves the branch only when it succeeds.

`imp done` runs configured checks, shows the complete candidate diff, asks once, integrates locally, then removes the feature worktree, branch, claim, and record.

Humans and agents may edit the current checkout for focused work. Use `imp start` for parallel, large, risky, or clean-checkout work.

## AI

Only `imp commit` sends content to AI: the selected diff, for a message. Pass `-m` to send nothing. `imp doctor` only sends a fixed ping; every other command is deterministic. Imp detects the actor automatically.

## State

Imp keeps one compact file per open feature in Git's common directory. `done` and `worktree remove` delete it. Plans and diffs live only for the process; locks and temporary files are transient. Releases remain in Git and GitHub. Defaults do not create a config file.

## Multiple repositories

```bash
imp start checkout --repo api --repo web
imp done checkout
```

Run these from the directory containing the repositories. The repeated `--repo` order is the integration order.

## Automation

```bash
imp commit --json --dry-run
imp commit --json --yes
```

`--json` never prompts. `--dry-run` emits the exact ephemeral plan. `--yes` approves it.

## Git passthrough

Unknown commands run as Git with the same arguments and exit status.

```bash
imp diff --staged
imp log --oneline
imp push
```

Native commands are `commit`, `doctor`, `done`, `pr`, `release`, `start`, `status`, and `worktree`.

## Repository policy

Optional policy lives in `.imp`:

```json
{
   "check:commands": [
      { "name": "test", "run": ["uv", "run", "pytest"] }
   ]
}
```

`imp pr` pushes the current branch and opens or updates its pull request. `--into develop` targets another branch instead of trunk.

`imp release` increments the patch version, tags the current clean commit, pushes, and publishes. Use an explicit version or `--major`, `--minor`, `--patch`, `--rc`, or `--stable`. `--local` only creates the tag.

See the [documentation](https://docs.katforge.com/packages/imp/) and [JSON protocol](https://docs.katforge.com/packages/imp/json-protocol).

## License

[MIT](LICENSE)
