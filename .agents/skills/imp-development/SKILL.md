---
name: imp-development
description: Use for source-code changes in Git repositories. Route every Git operation through Imp, isolate concurrent work with managed worktrees, and span one feature across repositories when they must move together.
---

# Imp development

1. Discover before changing anything.

   - Every command takes `--json` and answers with one versioned envelope; failures use `imp.error.v1` and a nonzero exit.
   - `--json` already implies `--no-input`, so a missing answer fails loudly instead of waiting. Pass `--yes` to approve what you already decided, and `--dry-run` to see a plan without applying it.
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
   - `imp review <name>` and `imp done <name>` then cover every member.

4. Use Imp for every Git operation.

   - Read with `imp status`, `imp diff`, `imp log`, `imp show`, or `imp blame`.
   - Run ordinary Git commands through Imp's passthrough, never through raw Git.
   - Prepare an exact commit plan at a coherent milestone and apply it without asking.
   - Commit and integrate to trunk freely. Never push as part of a commit.
   - Changing a remote needs approval first. Pushing and the QA release that follows are one grant; production is a second grant, often given in the same breath.
   - Read intent, not wording. Any plain request to send work up grants the push and QA bundle. Without the production grant, stop at QA and say so.
   - `imp done` lands a feature on trunk locally. `imp pr` proposes a branch for review. `imp release` cuts a version, and `--local` keeps it off the remote.
   - Release notes are built from commit subjects, so write every subject as the line you want published.
   - Anything that reaches a changelog or release notes is one short line each, major points only. Never a wrapped paragraph, never an entry per incidental commit.

5. Keep authorship human.

   - Never identify an agent, model, provider, or bot as an author or contributor, and never add attribution or co-author trailers.
   - Preserve the configured human Git identity. Keep actor IDs in local state and machine output.

6. Finish cleanly.

   - Run configured checks, then `imp status --json` before handoff.
   - Release the writer claim when editing stops, and remove worktrees and branches once they are merged into trunk.
   - `imp status` reports interrupted operations with their resume command; leave blocked features and spans in place for it.
   - Never write repository instruction files unless explicitly requested.
