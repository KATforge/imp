---
name: imp-development
description: Use for source-code changes in Git repositories. Route every Git operation through Imp, isolate concurrent work with managed worktrees, and use Temper only for coupled repositories or shared local runtimes.
---

# Imp development

1. Discover before changing anything.

   - Outside Git, edit directly. Do not initialize Git or Imp.
   - Inside Git, run `imp status --json`.
   - Run `temper --json status` when a `temper.yaml` workspace owns the repository.
   - Never create `.imp` or `temper.yaml` automatically.

2. Choose the smallest safe editing surface.

   - Edit focused changes in the current checkout when the user allows it.
   - Use `imp start <name> --task <intent> --use --yes --json` for parallel, large, risky, or clean-checkout work.
   - Reuse a managed feature only when it matches the task.
   - Never create a provider-owned worktree or edit another actor's claimed worktree.

3. Use Temper only when sources must move or run together.

   - Create one change for coupled repositories.
   - Use targeted `dev` or `review` leases for interactive runtime work.
   - Use an immutable `test` lease for release-gating tests.
   - Do not start a full stack for repository-local work.

4. Use Imp for every Git operation.

   - Read with `imp status`, `imp diff`, `imp log`, `imp show`, or `imp blame`.
   - Run ordinary Git commands through Imp's passthrough, never through raw Git.
   - Prepare an exact commit plan at a coherent milestone.
   - Apply it only after explicit commit approval.
   - Never push as part of a commit.

5. Keep authority separate.

   - Require separate approval for commit, push, integration, release, and deployment.
   - Only a human may mark an Imp candidate reviewed.

6. Keep authorship human.

   - Never identify an agent, model, provider, or bot as an author or contributor.
   - Never add attribution, signatures, generated-by notices, or co-author trailers.
   - Preserve the configured human Git identity.
   - Keep actor IDs in local state and machine output.

7. Finish cleanly.

   - Run configured checks.
   - Run `imp status --json` before handoff.
   - Release the writer claim when editing stops.
   - Preserve blocked features and Temper changes for recovery.
   - Never write repository instruction files unless the user explicitly requests one.
