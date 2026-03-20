from typing import Optional

import typer

from imp import console, git


def done (
   target: Optional [str] = typer.Argument (None, help="Branch to merge into"),
):
   """Merge feature branch into target, then clean up.

   Merges the current branch into a target branch (defaults to main/master),
   then deletes the feature branch locally and remotely. If the branch was
   already merged via PR, pulls the target instead of merging locally.
   """

   git.require ()
   git.require_clean ("imp commit first")

   feature = git.branch ()
   base = target or git.base_branch ()

   if feature == base:
      console.err (f"Already on {base}")
      console.hint ("switch to a feature branch first")
      raise typer.Exit (1)

   if target and not git.rev_parse (target):
      if git.remote_has_branch (target):
         git.checkout (target)
         git.checkout (feature)
      else:
         console.err (f"Branch {target} does not exist")
         raise typer.Exit (1)

   console.header ("Done")

   git.fetch (prune=True)

   already_merged = False
   remote_base = f"origin/{base}"
   if git.rev_parse (remote_base):
      already_merged = git.is_merged (feature, remote_base)

   has_remote_feature = git.remote_has_branch (feature)

   console.label (f"{feature} → {base}")
   console.out.print ()
   console.item (f"Switch to {base}")

   if already_merged:
      console.item (f"Pull latest (already merged remotely)")
   else:
      console.item (f"Merge {feature} into {base} (--no-ff)")

   console.item (f"Delete {feature} (local)")

   if has_remote_feature:
      console.item (f"Delete {feature} (remote)")

   console.out.print ()

   if not console.confirm ("Proceed?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   git.checkout (base)

   if already_merged:
      git.pull ()
      console.success (f"Pulled {base} (already merged)")
   else:
      if git.has_upstream ():
         git.pull ()

      if not git.merge (feature, no_ff=True):
         console.err (f"Merge conflict")
         console.hint (f"resolve conflicts, then: git merge --continue")
         raise typer.Exit (1)

      console.success (f"Merged {feature} into {base}")

   if git.delete_branch (feature):
      console.success (f"Deleted local branch {feature}")
   else:
      console.warn (f"Branch {feature} has unmerged changes")
      console.out.print ()
      if console.confirm (f"Force delete {feature}?"):
         git.delete_branch (feature, force=True)
         console.success (f"Force deleted local branch {feature}")
      else:
         console.muted (f"Kept local branch {feature}")

   if has_remote_feature:
      git.delete_branch (feature, remote=True)
      console.success (f"Deleted remote branch {feature}")

   console.hint ("imp branch to start something new")
