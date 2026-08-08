---
name: imp-development
description: Use for source-code changes in Git repositories. Allow direct edits outside Git, route Git state changes through Imp, and use Temper only for coupled repositories or shared local runtimes.
---

# Imp development

Codex users MUST review newly installed or changed Imp hooks once through `/hooks`.
Until that review succeeds, `imp doctor --agents` reports the Codex adapter as `guided`.

1. Discover before changing anything.

   - Outside Git, edit directly. Do not initialize Git or Imp.
   - Inside Git, run `imp status --json`.
   - Run `temper --json status` when a `temper.yaml` workspace owns the repository.
   - Never create `.imp` or `temper.yaml` automatically.

2. Choose the editing surface by judgment.

   - Small, focused changes: edit inline in the current checkout.
   - Parallel lanes, large or risky changes, or a checkout that must stay clean: run `imp start <name> --task <intent> --use --yes --json` and work in the returned worktree.
   - Reuse the current managed feature only when it matches the task.
   - Never create a provider-owned worktree.
   - Never edit inside another actor's claimed worktree.

3. Use Temper only when sources must move or run together.

   - Create one change for coupled repositories.
   - Use a targeted `dev` or `review` lease for interactive runtime work.
   - Use an immutable `test` lease for release-gating tests.
   - Reclaim idle runtimes with `temper lease reclaim`; break a dead session's lock with `temper unlock`.
   - Do not start a full stack for repository-local work.

4. Use Imp for every Git operation.

   - Read with `imp status`, `imp diff`, `imp log`, `imp show`, or `imp blame`.
   - Prepare an exact commit plan at a coherent milestone.
   - Apply it only after approval for that commit.
   - The guard is advisory: raw `git` is not blocked, it emits a reminder to use the Imp equivalent. Route git through Imp anyway.
   - Get the user's approval before any commit, push, or integration.
   - Never push as part of a commit.

5. Keep authority separate.

   - Commit, push, integration (`imp done`, `temper done`), release, and deployment require separate approval.
   - Only a human may mark an Imp candidate reviewed.

6. Keep authorship human.

   - Never identify an AI agent, model, provider, or bot as an author or contributor.
   - Never add AI attribution, signatures, generated-by notices, or co-author trailers.
   - Preserve the configured human Git identity.
   - Keep actor IDs in local state and machine output.

7. Finish cleanly.

   - Run configured checks.
   - Run `imp status --json` before handoff.
   - Release the writer claim when editing stops.
   - Preserve blocked features and Temper changes for recovery.
   - Never write repository agent-instruction files.
