# Imp JSON protocol

Pass global `--json` for one JSON document on standard output.

```bash
imp -C /repo --actor-id actor:codex:session-42 --json status
imp -C /repo --actor-id actor:codex:session-42 --json done checkout --plan
imp -C /repo --actor-id actor:codex:session-42 --json done --apply plan:done:checkout:1 --yes
```

Every result uses this envelope:

```json
{
   "schema": "imp.<result>.v1",
   "command": "imp <command>",
   "ok": true,
   "data": {},
   "warnings": []
}
```

A failed native command exits nonzero and emits the same envelope with `ok` false, schema `imp.error.v1`, and the failure message in `data.message`:

```json
{
   "schema": "imp.error.v1",
   "command": "imp commit",
   "ok": false,
   "data": { "message": "Not a git repository" },
   "warnings": []
}
```

Saved operation plans use `imp.plan.v1` and a command-specific payload schema.

| Operation | Result or payload schema |
|---|---|
| Repository status | `imp.status.v1` |
| Feature start plan | `imp.start-plan.v1` |
| Commit plan | `imp.commit-plan.v2` |
| Integration plan | `imp.done-plan.v1` |
| Human review receipt | `imp.review.v1` |
| Guard grant | `imp.guard.v1` |
| Guard list | `imp.guards.v1` |
| Guard revocation | `imp.guard-revoke.v1` |
| Source-release plan | `imp.ship-plan.v2` |
| Source-release receipt | `imp.release.v1` envelope with `imp.source-release.v2` persisted data |
| Command failure | `imp.error.v1` |

Automation must capture the returned `plan_id`, then apply that exact plan with `--apply <plan-id> --yes`. It must not parse human output or read Imp’s internal state files.

Schema versions are independent of the Imp package version. Additive optional fields retain the current schema. Incompatible field or semantic changes require the next schema version.
