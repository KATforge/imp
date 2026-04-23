import json
import re
from pathlib import Path

import typer

from imp import ai, console, git, prompts, version

MAX_DIFF_LINES = 3000

def _build_version_map (
   tags: dict [str, str],
   commits: list [dict [str, str]],
) -> list [dict]:
   # Reverse lookup: commit hash -> tag
   hash_to_tag = { v: k for k, v in tags.items () }

   versions = []
   current_commits = []
   current_date = ""

   for entry in commits:
      current_commits.append (entry)
      current_date = entry ["date"]

      tag = hash_to_tag.get (entry ["hash"])
      if tag:
         versions.append ({
            "version": tag.lstrip ("v"),
            "date": current_date,
            "commits": list (current_commits),
         })
         current_commits = []

   # Remaining commits after last tag
   if current_commits:
      versions.append ({
         "version": "Unreleased",
         "date": current_date,
         "commits": list (current_commits),
      })

   return versions

def _infer_versions (
   commits: list [dict [str, str]],
) -> list [dict]:
   subjects = "\n".join (c ["subject"] for c in commits)
   prompt = prompts.changelog_infer (subjects)

   try:
      raw = ai.fast (prompt)
      groups = json.loads (raw.strip ())
   except (json.JSONDecodeError, ValueError):
      return [ {
         "version": "Unreleased",
         "date": commits [-1] ["date"] if commits else "",
         "commits": list (commits),
      } ]

   # Build a subject -> commit lookup
   subject_to_commit = {}
   for c in commits:
      subject_to_commit [c ["subject"]] = c

   versions = []
   for group in groups:
      ver = group.get ("version", "Unreleased")
      group_commits = []
      last_date = ""
      for subj in group.get ("commits", []):
         if subj in subject_to_commit:
            group_commits.append (subject_to_commit [subj])
            last_date = subject_to_commit [subj] ["date"]

      if group_commits:
         versions.append ({
            "version": ver,
            "date": last_date,
            "commits": group_commits,
         })

   # Any commits the AI missed go into Unreleased
   assigned = set ()
   for v in versions:
      for c in v ["commits"]:
         assigned.add (c ["hash"])

   missed = [ c for c in commits if c ["hash"] not in assigned ]
   if missed:
      versions.append ({
         "version": "Unreleased",
         "date": missed [-1] ["date"],
         "commits": missed,
      })

   return versions

def _collect_diffs (commits: list [dict [str, str]]) -> str:
   parts = []
   total = 0

   for c in commits:
      patch = git.show_patch (c ["hash"])
      if not patch:
         continue

      lines = patch.splitlines ()
      if total + len (lines) > MAX_DIFF_LINES:
         remaining = MAX_DIFF_LINES - total
         if remaining > 0:
            parts.append ("\n".join (lines [:remaining]))
         break

      parts.append (patch)
      total += len (lines)

   return "\n".join (parts)

def _entry_from_diffs (commits: list [dict [str, str]]) -> str:
   diffs = _collect_diffs (commits)

   if not diffs:
      subjects = "\n".join (c ["subject"] for c in commits)
      return version.changelog_from_commits (subjects)

   prompt = prompts.changelog_entry (diffs)
   result = ai.smart (prompt)
   return ai.strip_fences (result).strip ()

def _generate_changelog (versions: list [dict]) -> str:
   lines = [
      "# Changelog",
      "",
      "All notable changes to this project will be documented in this file.",
      "",
   ]

   # Reverse so newest version is first
   for ver in reversed (versions):
      v = ver ["version"]
      d = ver ["date"]

      if v == "Unreleased":
         lines.append ("## [Unreleased]")
      else:
         lines.append (f"## [{v}] - {d}")

      lines.append ("")

      console.muted (f"Analyzing {v} ({len (ver ['commits'])} commits)...")
      console.out.print ()

      entry = _entry_from_diffs (ver ["commits"])
      if entry:
         lines.append (entry)
      lines.append ("")

   return "\n".join (lines).rstrip () + "\n"

def _tag_plan (
   versions: list [dict],
   existing_tags: dict [str, str],
) -> list [dict]:
   plan = []

   for ver in versions:
      v = ver ["version"]
      if v == "Unreleased":
         continue

      tag_name = f"v{v}"
      # Last commit in the version is the tag point
      target_hash = ver ["commits"] [-1] ["hash"]

      if tag_name not in existing_tags:
         plan.append ({
            "tag": tag_name,
            "hash": target_hash,
            "action": "create",
         })
      elif existing_tags [tag_name] != target_hash:
         plan.append ({
            "tag": tag_name,
            "hash": target_hash,
            "old_hash": existing_tags [tag_name],
            "action": "move",
         })

   return plan

def _apply_tags (plan: list [dict]):
   for item in plan:
      if item ["action"] == "move":
         git.tag_delete (item ["tag"])
      git.tag (item ["tag"], ref=item ["hash"])
      console.success (f"Tagged {item ['tag']} at {item ['hash'] [:7]}")

def changelog (
   since: str = typer.Option ("", "--since", "-s", help="Date, tag, or commit hash to start from"),
   apply: bool = typer.Option (False, "--apply", help="Create missing/corrected git tags"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Skip confirmations"),
):
   """Regenerate CHANGELOG.md from git history.

   Walks commit history, maps existing tags to version boundaries,
   uses AI to infer boundaries for untagged regions, and generates
   a complete changelog. Optionally creates missing git tags.
   """

   git.require ()

   console.header ("Changelog")

   # Resolve --since to a commit ref
   since_ref = (since or "").strip ()
   since_commit = ""

   if since_ref:
      if re.match (r"^\d{4}$", since_ref):
         since_ref = f"{since_ref}-01-01"

      if re.match (r"^\d{4}-\d{2}-\d{2}$", since_ref):
         since_commit = git.log_after_date (since_ref)
         if not since_commit:
            console.fatal (f"No commits found after {since_ref}")
         console.muted (f"Starting from first commit after {since_ref}")
      else:
         since_commit = git.rev_parse (since_ref)
         if not since_commit:
            console.fatal (f"Could not resolve: {since_ref}")
         console.muted (f"Starting from {since_ref}")

   # Gather data
   tags = git.tag_commit_map ()
   commits = git.log_full (since=since_commit)

   if not commits:
      console.muted ("No commits found")
      raise typer.Exit (0)

   console.muted (f"Found {len (commits)} commits, {len (tags)} tags")

   # Build version map from tagged regions
   version_map = _build_version_map (tags, commits)

   # If the only entry is Unreleased and there are no tags in scope,
   # use AI to infer version boundaries
   all_unreleased = len (version_map) == 1 and version_map [0] ["version"] == "Unreleased"

   if all_unreleased and len (commits) > 1:
      console.muted ("No tags found, inferring versions with AI...")
      console.out.print ()

      version_map = _infer_versions (commits)

   # Generate changelog
   content = _generate_changelog (version_map)

   console.divider ()
   console.md (content)
   console.divider ()
   console.out.print ()

   # Write CHANGELOG.md
   if not yes:
      if not console.confirm ("Write CHANGELOG.md?"):
         console.muted ("Cancelled")
         raise typer.Exit (0)

   root = git.repo_root ()
   changelog_path = Path (root) / "CHANGELOG.md"
   changelog_path.write_text (content)
   console.success ("Wrote CHANGELOG.md")

   # Tag plan
   plan = _tag_plan (version_map, tags)

   if plan:
      console.out.print ()
      console.label ("Tag plan")
      for item in plan:
         action = item ["action"]
         tag = item ["tag"]
         short = item ["hash"] [:7]
         if action == "create":
            console.item (f"create {tag} at {short}")
         elif action == "move":
            old_short = item ["old_hash"] [:7]
            console.item (f"move   {tag}: {old_short} → {short}")

      console.out.print ()

      if apply:
         if not yes:
            if not console.confirm ("Apply tag changes?"):
               console.muted ("Skipped tag changes")
               return

         _apply_tags (plan)
      else:
         console.hint ("run with --apply to create these tags")
   else:
      console.muted ("All tags are correct")
