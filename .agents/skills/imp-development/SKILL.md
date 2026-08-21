---
name: imp-development
description: Use for source-code changes in Git repositories. Route every Git operation through Imp, work trunk-first under the trunk lock, isolate on contention with managed worktrees, and span one feature across repositories when they must move together.
---

# Imp development

1. Discover before changing anything.

   - Every command takes `--json` and answers with one versioned envelope; failures use `imp.error.v1` and a nonzero exit.
   - Git is the database: a feature is its `feature/*` branch plus its worktree; layers live under `refs/imp/layer`, discards under `refs/imp/attic`, and locks, span order, and knobs in `git config imp.*`. Imp writes no state files.
   - `imp commit` and `imp pr` send their diffs to AI for a message or description (`-m` sends nothing); `imp review` and `imp cleanup` send diffs for annotations and verdicts; `imp release` condenses commit subjects into notes; `imp doctor` only pings; `start`, `done`, `undo`, and `status` are deterministic. Everything generated stays terse and essentials-only.
   - Imp detects the current actor automatically. Never pass or persist an actor override.
   - Run `imp doctor --json` when the environment looks wrong; it reports tools, provider, and the effective `imp.*` configuration.
   - Outside Git, edit directly. Do not initialize Git or Imp.
   - Inside Git, run `imp status --json`. Run it from a directory of checkouts to cover every repository below it.

2. Start trunk-first and let Imp choose the surface.

   - `imp start <name> --json` claims the trunk lock when trunk is free, clean, and checked out: work then lands directly on trunk, live for the local runtime, and the session is one undoable layer. A busy or dirty trunk isolates in a managed worktree automatically; concurrent agents cascade — first takes trunk, the rest take worktrees.
   - Pass `--worktree` for deliberately parallel, large, or risky work; pass `--ticket SPK-12345` when the task names one, and it reaches branch names and commit subjects on its own.
   - Never create a provider-owned worktree, never edit inside another actor's worktree, and never work on a trunk whose lock another actor holds — `imp status` shows the holder.

3. Span repositories only when they must move together.

   - Create one feature for all of them: `imp start <name> --repo <alias> --repo <alias>`, run from the directory holding the checkouts. `--repo` takes a repository directory or a unique suffix, and the order named is the order they integrate.
   - Nothing is declared: a feature spans the repositories that share its branch name, and a lone checkout is a workspace of one.
   - `imp done <name>` then covers every member, dependency-first, refusing as a whole if any member is blocked.

4. Use Imp for every Git operation.

   - Read with `imp status`, `imp diff`, `imp log`, `imp show`, or `imp blame`; unknown commands pass through to Git unchanged.
   - Commit at coherent milestones with `imp commit --json`; approval is automatic for agents on `start`, `commit`, and `done`, so do not pass `--yes` for those. Destructive or remote commands (`undo`, `cleanup`, `worktree remove`, `pr`, `release`) still require `--yes`, which represents a human grant.
   - `imp done` integrates a worktree feature (checks, exact candidate, compare-and-swap) or releases a trunk session; `--all` lands every open feature oldest-first. Complete a feature when the task says to integrate, merge, or finish it.
   - `imp undo --yes` backs the newest unpushed layer off trunk and restores it as a feature worktree; use it when integrated work fails trunk testing, then fix and `imp done` again.
   - `imp review` is the human's annotated diff of unpushed trunk; run it only when asked.
   - Never push as part of a commit. Changing a remote needs approval first: pushing and the QA release that follows are one grant; production is a second grant, often given in the same breath. Read intent, not wording — any plain request to send work up grants the push and QA bundle; without the production grant, stop at QA and say so.
   - `imp release` increments patch by default; use a version or `--major`, `--minor`, `--patch`, `--rc`, or `--stable`; `--local` only tags. Release notes are the commit subjects since the previous tag, so keep every subject short and publishable.

5. Keep authorship human.

   - Never identify an agent, model, provider, or bot as an author or contributor, and never add attribution or co-author trailers.
   - Preserve the configured human Git identity. Keep actor IDs in local state and machine output.

6. Finish cleanly.

   - Run the project checks, then `imp status --json` before handoff.
   - Always end a trunk session with `imp done` before handoff: it releases the trunk lock and records the session as one undoable layer. A lock left behind blocks every other actor until it expires.
   - `imp done` removes what it integrates and releases what it locked. Use `imp worktree remove --yes` only when told to discard clean unfinished work; the tip parks in the attic for 30 days.
   - `imp cleanup` reconciles and flattens every open feature; run it only when asked, and leave holds in place for the next run.
   - Leave blocked features, spans, and foreign locks alone. Never write repository instruction files unless explicitly requested.
