import json
import re
from pathlib import Path

import typer

from imp import ai, console, git, prompts, version

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

def _entry_from_diffs (commits: list [dict [str, str]], fast: bool = False) -> str:
   return version.entry (commits, fast=fast)

def _generate_changelog (versions: list [dict], fast: bool = False) -> str:
   lines = [ version.HEADER.rstrip ("\n"), "" ]

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

      entry = _entry_from_diffs (ver ["commits"], fast=fast)
      if entry:
         lines.append (entry)
      lines.append ("")

   return "\n".join (lines).rstrip () + "\n"

def _upsert_unreleased (path: Path, entry: str):
   """Prepend the Unreleased block, replacing an existing Unreleased section in
   place so repeated runs never stack duplicate headers. A dated version block
   (from a release) is left untouched above it."""
   block = f"## [Unreleased]\n\n{entry}"

   if not path.is_file ():
      path.write_text (f"{version.HEADER}\n{block}\n")
      return

   lines = path.read_text ().splitlines (keepends=True)

   first = next ((i for i, line in enumerate (lines) if line.lstrip ().startswith ("## ")), None)

   if first is not None and lines [first].lstrip ().startswith ("## [Unreleased]"):
      end = next ((j for j in range (first + 1, len (lines)) if lines [j].lstrip ().startswith ("## ")), len (lines))
      path.write_text ("".join (lines [:first]) + block + "\n\n" + "".join (lines [end:]))
   else:
      version.write_changelog (path, block)

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

def _resolve_since (since_ref: str) -> str:
   """Turn a --since value (date, year, tag, or hash) into a commit ref."""
   if re.match (r"^\d{4}$", since_ref):
      since_ref = f"{since_ref}-01-01"

   if re.match (r"^\d{4}-\d{2}-\d{2}$", since_ref):
      since_commit = git.log_after_date (since_ref)
      if not since_commit:
         console.fatal (f"No commits found after {since_ref}")
      console.muted (f"Starting from first commit after {since_ref}")
      return since_commit

   since_commit = git.rev_parse (since_ref)
   if not since_commit:
      console.fatal (f"Could not resolve: {since_ref}")
   console.muted (f"Starting from {since_ref}")
   return since_commit

def _incremental (since: str, yes: bool, fast: bool, changelog_path: Path):
   """Default mode: top up the Unreleased section from commits since the last
   tag (or --since), leaving released history and hand edits alone."""
   tag = git.last_tag ()
   since_ref = (since or "").strip () or tag

   commits = git.log_full (since=since_ref) if since_ref else git.log_full ()

   if not commits:
      console.muted (f"No new commits since {since_ref or 'the start'}")
      raise typer.Exit (0)

   console.muted (f"{len (commits)} commit(s) since {since_ref or 'the start'}")
   console.out.print ()

   new_entry = version.entry (commits, fast=fast)
   if not new_entry.strip ():
      console.muted ("Nothing to add (every commit was skipped)")
      raise typer.Exit (0)

   console.divider ()
   console.md (f"## [Unreleased]\n\n{new_entry}")
   console.divider ()
   console.out.print ()

   if not yes and not console.confirm ("Update CHANGELOG.md?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   _upsert_unreleased (changelog_path, new_entry)
   console.success ("Updated CHANGELOG.md")
   console.hint ("imp changelog --rebuild to regenerate the whole file from history")

def _rebuild (since: str, apply: bool, yes: bool, fast: bool, changelog_path: Path):
   """Regenerate the entire file from git history, mapping tags to version
   boundaries and inferring untagged ones with AI."""
   since_commit = ""
   if (since or "").strip ():
      since_commit = _resolve_since (since.strip ())

   tags = git.tag_commit_map ()
   commits = git.log_full (since=since_commit)

   if not commits:
      console.muted ("No commits found")
      raise typer.Exit (0)

   console.muted (f"Found {len (commits)} commits, {len (tags)} tags")

   version_map = _build_version_map (tags, commits)

   all_unreleased = len (version_map) == 1 and version_map [0] ["version"] == "Unreleased"

   if all_unreleased and len (commits) > 1:
      console.muted ("No tags found, inferring versions with AI...")
      console.out.print ()
      version_map = _infer_versions (commits)

   content = _generate_changelog (version_map, fast=fast)

   console.divider ()
   console.md (content)
   console.divider ()
   console.out.print ()

   if not yes and not console.confirm ("Write CHANGELOG.md?"):
      console.muted ("Cancelled")
      raise typer.Exit (0)

   changelog_path.write_text (content)
   console.success ("Wrote CHANGELOG.md")

   plan = _tag_plan (version_map, tags)

   if not plan:
      console.muted ("All tags are correct")
      return

   console.out.print ()
   console.label ("Tag plan")
   for item in plan:
      action = item ["action"]
      tag = item ["tag"]
      short = item ["hash"] [:7]
      if action == "create":
         console.item (f"create {tag} at {short}")
      elif action == "move":
         console.item (f"move   {tag}: {item ['old_hash'] [:7]} → {short}")
   console.out.print ()

   if not apply:
      console.hint ("run with --apply to create these tags")
      return

   if not yes and not console.confirm ("Apply tag changes?"):
      console.muted ("Skipped tag changes")
      return

   _apply_tags (plan)

def changelog (
   since: str = typer.Option ("", "--since", "-s", help="Date, tag, or commit hash to start from"),
   apply: bool = typer.Option (False, "--apply", help="With --rebuild: create missing/corrected git tags"),
   rebuild: bool = typer.Option (False, "--rebuild", help="Regenerate the entire file from git history"),
   fast: bool = typer.Option (False, "--fast", help="Use the deterministic subject-based entry (no AI)"),
   yes: bool = typer.Option (False, "--yes", "-y", help="Skip confirmations"),
):
   """Update CHANGELOG.md from git history.

   By default, tops up the [Unreleased] section from the commits since the last
   tag using a diff-aware AI entry (the same engine imp release uses). Pass
   --rebuild to regenerate the whole file from history, mapping tags to version
   boundaries and inferring untagged ones. --fast swaps the AI for the
   deterministic subject-based entry.
   """

   git.require ()

   console.header ("Changelog")

   changelog_path = Path (git.repo_root ()) / "CHANGELOG.md"

   if rebuild:
      _rebuild (since, apply, yes, fast, changelog_path)
   else:
      _incremental (since, yes, fast, changelog_path)
