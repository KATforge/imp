---
name: imp-development
description: Use for source-code changes in Git repositories. Allow direct edits outside Git, route repository state through Imp, and use Temper only for coupled repositories or shared local runtimes.
---

# Imp development

Codex users MUST review newly installed or changed Imp hooks once through `/hooks`.
Until that review succeeds, `imp doctor --agents` reports the Codex adapter as `guided`.

1. Discover before changing anything.

   - Outside Git, edit directly. Do not initialize Git or Imp.
   - Inside Git, run `imp status --json`.
   - Run `temper status --json` when a `temper.yaml` workspace owns the repository.
   - Never create `.imp` or `temper.yaml` automatically.

2. Attach before the first source mutation in Git.

   - If the user explicitly requests direct edits in the current checkout, run `imp guard request direct-edit` as a standalone provider-approved command.
   - In Codex, request elevated execution so `PermissionRequest` shows the approval. Claude prompts through `PreToolUse`.
   - Never request the exception without explicit user direction. It applies only to this repository and session for 30 minutes.
   - Reuse the current managed feature only when it matches the task.
   - Otherwise run `imp start <name> --task <intent> --use --yes --json`.
   - Use the returned worktree as the only writable source root.
   - Never create a provider-owned worktree.

3. Use Temper only when sources must move or run together.

   - Create one change for coupled repositories.
   - Use a targeted `dev` or `review` lease for interactive runtime work.
   - Use an immutable `test` lease for release-gating tests.
   - Do not start a full stack for repository-local work.

4. Use Imp for every Git operation.

   - Read with `imp status`, `imp diff`, `imp log`, `imp show`, or `imp blame`.
   - Prepare an exact commit plan at a coherent milestone.
   - Apply it only after approval for that commit.
   - Never push as part of a commit.

5. Keep authority separate.

   - Commit, push, integration, release, and deployment require separate approval.
   - Only a human may mark an Imp candidate reviewed.

6. Keep authorship human.

   - Never identify an AI agent, model, provider, or bot as an author or contributor.
   - Never add AI attribution, signatures, generated-by notices, or co-author trailers.
   - Preserve the configured human Git identity.
   - Keep actor IDs in local state and machine output.

7. Finish cleanly.

   - Run configured checks.
   - Run `imp status --json` before handoff.
   - Revoke temporary direct-edit access with `imp guard revoke`; session shutdown also revokes it.
   - Release the writer claim when editing stops.
   - Preserve blocked features and Temper changes for recovery.
   - Never write repository agent-instruction files.
