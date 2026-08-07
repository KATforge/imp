---
name: katforge-development
description: Use for every source-code change. Allow direct filesystem edits outside Git without initialization; inside Git, route repository state through Imp, coordinate related repositories and runtime testing through Temper, and preserve explicit approval boundaries for commits, pushes, integration, releases, and deployment.
---

# KATforge development

Codex users MUST review newly installed or changed KATforge hooks once through `/hooks`.
Until that review succeeds, `imp doctor --agents` reports the Codex adapter as `guided`.

1. Discover before changing anything.

   - When the target is outside Git, edit it directly. Do not initialize Git or Imp.
   - Otherwise run `imp status --json` in the repository.
   - Run `temper status --json` when `temper.yaml` exists above it.
   - Keep read-only inspection in the current source tree.

2. Inside Git, attach before the first source mutation.

   - Reuse the current managed feature only when it matches the user's work.
   - Otherwise run `imp start <name> --task <intent> --use --actor-id <resolved-actor> --yes --json`.
   - Keep an open-ended name honest when the outcome is unknown, such as `checkout-lane`.
   - Capture the returned feature ID, claim, context path, and worktree path.
   - Use that returned path as the only writable source root.
   - Never create a provider-owned worktree.

3. Use Temper only when sources must move or run together.

   - Create one change with `temper change start` for coupled repositories.
   - Use a targeted `dev` or `review` lease only when runtime behavior needs it.
   - Use an immutable `test` lease for cross-repository or release-gating tests.
   - Do not start a full stack for a repository-local edit.

4. Use Imp for every Git operation.

   - Read with `imp status`, `imp diff`, `imp log`, `imp show`, or `imp blame`.
   - At a coherent milestone, prepare `imp commit --plan --json`.
   - Apply a commit plan only after the user approves that exact commit operation.
   - Never push as part of a commit.

5. Keep authority separate.

   - A commit approval does not approve a push.
   - A review receipt does not approve integration.
   - An integration approval does not approve release or deployment.
   - Only a human actor may mark an Imp candidate reviewed.

6. Keep authorship human.

   - Never identify an AI agent, model, provider, or bot as an author, co-author, contributor, or generator of the work.
   - Never add `Co-Authored-By`, AI attribution trailers, signatures, or generated-by notices.
   - Preserve the configured human Git identity.
   - Keep resolved Imp and Temper actor IDs in local state and machine output. Never copy a live actor identity into repository, collaboration, or release content.

7. Finish cleanly.

   - Run configured checks.
   - Run `imp status --json` before handoff.
   - Release the writer claim when the session stops editing.
   - Preserve blocked features and Temper changes for recovery.
   - Never write repository `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, or equivalent provider instructions.
