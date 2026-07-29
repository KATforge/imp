from collections.abc import Callable

import typer

from imp import console, git

def integrate (
   ref: str,
   *,
   strategy: str = "merge",
   no_ff: bool = False,
   whisper: str = "",
   favor_ours: bool = False,
   favor_theirs: bool = False,
   auto: bool = False,
) -> bool:
   """Merge or rebase <ref> into the current branch; on conflict, hand off to
   the AI resolve flow and finalize. One conflict path shared by merge, pull,
   and sync. Returns True once the integration lands (clean or resolved)."""
   from imp.commands.resolve import resolve as resolve_cmd

   rebasing = strategy == "rebase"

   if rebasing:
      clean = git.rebase (ref)
      in_progress = git.rebase_in_progress
      finish = git.rebase_continue
      abort_hint = "git rebase --abort"
      verb = "Rebase"
   else:
      clean = git.merge (ref, no_ff=no_ff)
      in_progress = git.merge_in_progress
      finish = git.merge_continue
      abort_hint = "git merge --abort"
      verb = "Merge"

   if clean:
      return True

   if not in_progress ():
      console.fatal (f"{verb} failed (not in conflict state); check the error above")

   conflicts = git.conflicts ()
   console.warn (f"{len (conflicts)} conflict(s); handing off to resolve")
   console.out.print ()

   try:
      resolve_cmd (
         whisper=whisper,
         favor_ours=favor_ours,
         favor_theirs=favor_theirs,
         yes=auto,
      )
   except typer.Exit:
      pass

   remaining = git.conflicts ()
   if remaining:
      console.hint (f"imp resolve to finish, or {abort_hint}")
      console.fatal (f"{len (remaining)} conflict(s) still unresolved")

   if not finish ():
      console.fatal (f"Failed to finalize {verb.lower ()}")

   return True

def reconcile (fetch: bool = True) -> bool:
   """Integrate upstream into the current branch before publishing.

   Fetches, then no-ops when up to date or purely ahead. A clean rebase runs
   silently; overlapping edits stop, name the conflicting files, and offer the
   AI resolve path, so publishing never leaves the branch diverged. Pass
   fetch=False when origin was just fetched. Returns False when the caller
   must not push.
   """

   if not git.has_upstream ():
      return True

   if fetch:
      git.fetch ()

   behind = git.count_behind ()

   if behind == 0:
      return True

   ahead = git.count_ahead ()

   console.label ("Diverged" if ahead else "Behind")
   console.item (f"{ahead} ahead, {behind} behind" if ahead else f"{behind} commits")
   console.out.print ()

   if not git.is_clean ():
      console.hint ("imp commit, then retry")
      console.err ("Uncommitted changes; cannot rebase onto upstream")
      return False

   conflicts = git.merge_preview ("@{u}")

   if conflicts:
      console.warn (f"{len (conflicts)} file(s) conflict with upstream")

      for path in conflicts:
         console.item (path)

      console.out.print ()

      if console.choose ("Reconcile?", [ "Reconcile automatically", "Leave it" ]) == "Leave it":
         console.hint ("imp pull to reconcile with review")
         console.err ("Still diverged; nothing pushed")
         return False

   console.muted ("Rebasing onto upstream...")
   integrate ("@{u}", strategy="rebase", auto=True)
   console.success ("Rebased")
   console.out.print ()

   return True

def review_commit (
   msg: str,
   yes: bool,
   on_cancel: Callable [[], None] | None = None,
   **commit_kwargs,
) -> str:
   if yes:
      console.item (msg)
      git.commit (msg, **commit_kwargs)
      return msg

   choice = console.review (msg)

   if choice == "Edit":
      msg = console.edit (msg)

      if not msg.strip ():
         if on_cancel:
            on_cancel ()
         console.muted ("Empty message, cancelled")
         raise typer.Exit (0)

      git.commit (msg, **commit_kwargs)
   elif choice == "Yes":
      git.commit (msg, **commit_kwargs)
   else:
      if on_cancel:
         on_cancel ()
      console.muted ("Cancelled")
      raise typer.Exit (0)

   return msg
