---
name: imp-development
description: Use for source-code changes in Git repositories. Route every Git operation through Imp, isolate concurrent work with managed worktrees, and span one feature across repositories when they must move together.
---

# Imp development

1. Discover before changing anything.

   - Every command takes `--json` and answers with one versioned envelope; failures use `imp.error.v1` and a nonzero exit.
   - `--json` never prompts. Pass `--yes` to approve what you already decided, and `--dry-run` to see a plan without applying it.
   - Only `imp commit` sends content to AI: the selected diff, for a message. Pass `-m` to send nothing. Every other workflow command is deterministic; `imp doctor` only sends a fixed ping.
   - Imp detects the current actor automatically. Never pass or persist an actor override.
   - Run `imp doctor --json` when the environment looks wrong; it reports tools, provider, and configuration.
   - Outside Git, edit directly. Do not initialize Git or Imp.
   - Inside Git, run `imp status --json`. Run it from a directory of checkouts to cover every repository below it.
   - Never create `.imp` automatically.

2. Choose the smallest safe editing surface.

   - Edit focused changes in the current checkout.
   - Use `imp start <name> --yes --json` for parallel, large, risky, or clean-checkout work.
   - Reuse a managed feature only when it matches the task.
   - Never create a provider-owned worktree or edit another actor's claimed worktree.

3. Span repositories only when they must move together.

   - Create one feature for all of them: `imp start <name> --repo <alias> --repo <alias>`.
   - Run it from the directory holding the checkouts. `--repo` takes a repository directory or a unique suffix of one, and the order you name them is the order they integrate.
   - Nothing is declared: a feature spans the repositories that manage its name, and a lone checkout is a workspace of one.
   - `imp done <name>` then covers every member.

4. Use Imp for every Git operation.

   - Read with `imp status`, `imp diff`, `imp log`, `imp show`, or `imp blame`.
   - Run ordinary Git commands through Imp's passthrough, never through raw Git.
   - Prepare an exact commit plan at a coherent milestone and apply it without asking.
   - Commit and integrate to trunk freely. Never push as part of a commit.
   - Changing a remote needs approval first. Pushing and the QA release that follows are one grant; production is a second grant, often given in the same breath.
   - Read intent, not wording. Any plain request to send work up grants the push and QA bundle. Without the production grant, stop at QA and say so.
   - `imp done` lands a feature on trunk locally. `imp pr` proposes a branch for review; `--into <branch>` targets a nondefault base. `imp release` increments patch by default; use a version or `--major`, `--minor`, `--patch`, `--rc`, or `--stable`. `--local` only tags it.
   - Release notes contain the commit subjects since the previous tag, so keep every subject short and publishable.

5. Keep authorship human.

   - Never identify an agent, model, provider, or bot as an author or contributor, and never add attribution or co-author trailers.
   - Preserve the configured human Git identity. Keep actor IDs in local state and machine output.

6. Finish cleanly.

   - Run configured checks, then `imp status --json` before handoff.
   - `imp done` removes integrated features. Use `imp worktree remove` to discard clean unfinished features.
   - Leave blocked features and spans in place for the next run.
   - Never write repository instruction files unless explicitly requested.
