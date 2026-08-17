<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

<h1 align="center">Imp</h1>
<p align="center"><strong>Safe Git workstreams for people and parallel AI agents.</strong></p>

Imp gives each concurrent writer an isolated Git worktree and turns finished work into small, approved commits.

## Install

```bash
pip install imp-git
imp doctor
```

## Workflow

```bash
imp start payment-retries --task "Improve failed-payment recovery"
cd "$(imp worktree path payment-retries)"

# Edit and test.
imp commit --plan
imp commit --apply --yes

imp review
imp done --plan
imp done --apply --yes
```

Omitting an existing feature opens a picker. Review asks whether to mark the exact candidate after displaying it.

`imp start` branches from freshly verified remote trunk by default.

The plan creates no branch or worktree. Apply revalidates the exact base before changing Git state.

`imp commit` plans staged changes, or all dirty changes when nothing is staged. It can split separate change sections from the same file into different commits. Apply builds the complete commit chain off-ref and moves the branch only after every commit succeeds.

## Repository fleet

Consolidate every managed feature into the repository's native trunk and remove its clean local worktree and branch:

```bash
imp fleet --plan
imp fleet --apply plan:fleet:repository:1 --yes
```

`--into <branch>` overrides the target. `--strategy squash` is the default. Agent-written members retain Imp's exact human-review gate. Dirty, missing, claimed, or unmanaged feature state blocks the fleet without discarding anything.

To preserve feature branches and publish one pull request per feature instead:

```bash
imp fleet --pr --plan
imp fleet --apply plan:fleet:repository:2 --yes
```

## Direct editing

Humans and agents may use the current checkout for focused work when the user allows it. Use a managed worktree for parallel, large, risky, or clean-checkout work.

Existing checkouts still support incremental Imp adoption:
Repositories that must move together share one feature:

```bash
imp start checkout --repo api --repo web
imp review checkout
imp done checkout
```

Imp finds `workspace.yaml` by walking up from the working directory. Without one it is
simply the single-repository tool.

Agent clients use the provider-neutral [Imp development skill](.agents/skills/imp-development/SKILL.md). Imp requires no hooks or adapters.

## Documentation

See the [Imp documentation](https://docs.katforge.com/packages/imp/) for direct editing, parallel workstreams, repository policy, releases, and automation.

Imp stores feature records, plans, claims, and active selection under the repository's common Git directory. Nothing is written to project-level agent instruction files.

Repositories need no `.imp` file for built-in policy. Imp creates local state when an operation needs it. Adding tracked policy remains an explicit source change.

Imp resolves supported agent session identities from the environment. Other clients pass `--actor-id`.

## Automation

```bash
imp --json --no-input commit --plan
imp --json --no-input commit --apply plan:commit:payments:1 --yes
imp active --path
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

Native commands are `start`, `status`, `done`, `fleet`, `commit`, `review`, `pr`, `release`, `doctor`, `worktree`, and `recover`.

## Optional repository policy

Project overrides live in `.imp`:

```json
{
   "feature:required": false,
   "check:commands": [
      { "name": "test", "run": ["uv", "run", "pytest"] }
   ],
   "worktree:setup": [
      { "name": "dependencies", "run": ["uv", "sync"] }
   ],
   "worktree:share": [".env.local"]
}
```

Setup commands are argv arrays. Shared paths must be explicitly allowed, ignored, untracked, and inside the primary repository.

`imp release --minor` reads the highest existing tag, steps the version, then updates package versions, lockfiles, and the flat changelog before committing, tagging, pushing, and publishing the GitHub release. `--prerelease` cuts the next `-rc.N` instead.

`imp release --local` stops after the commit and the tag, touching no remote. Use it when you want a version cut locally and will publish later.

`imp pr --into main` pushes the current branch and opens or updates its pull request. It never tags or bumps a version, so it is the promotion path rather than a release.

The body is one short bullet per commit, oldest first. Each line keeps its first clause and clips at `commit:max_subject`, so a reviewer scans it instead of reading it.

See the [Imp documentation](https://docs.katforge.com/packages/imp/) for the complete workflow.
Machine clients should follow the [JSON protocol](https://docs.katforge.com/packages/imp/json-protocol).

## License

[MIT](LICENSE)
