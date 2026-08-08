<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

<h1 align="center">Imp</h1>
<p align="center"><strong>Safe Git workstreams for people and parallel AI agents.</strong></p>

Imp gives each concurrent writer an isolated Git worktree and turns finished work into small, approved commits.

## Install

```bash
pip install imp-git
imp config
imp doctor
```

## Workflow

```bash
imp start payment-retries --task "Improve failed-payment recovery" --use
cd "$(imp worktree path payment-retries)"

# Edit and test.
imp commit --plan
imp commit --apply --yes

imp review
imp done --plan
imp done --apply --yes
```

Agent clients use the provider-neutral [Imp development skill](.agents/skills/imp-development/SKILL.md). Imp requires no hooks or adapters.

## Documentation

See the [Imp documentation](https://docs.katforge.com/packages/imp/) for direct editing, parallel workstreams, repository policy, releases, and automation.

Machine clients should follow the [JSON protocol](https://docs.katforge.com/packages/imp/json-protocol).

## License

[MIT](LICENSE)
