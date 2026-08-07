import os
import re
import subprocess
from pathlib import Path

from imp_git import console

_SEMVER_TAG_RE = re.compile (r"^v\d+\.\d+\.\d+$")

def _run (
   *args: str,
   check: bool = True,
   timeout: int = 60,
   env: dict [str, str] | None = None,
) -> subprocess.CompletedProcess [str]:
   run_env = None
   if env:
      run_env = { **os.environ, **env }

   try:
      return subprocess.run (
         [ "git", *args ],
         capture_output=True,
         text=True,
         check=check,
         timeout=timeout,
         env=run_env,
      )
   except subprocess.TimeoutExpired:
      label = args [0] if args else "command"
      console.fatal (f"git {label} timed out")
   except subprocess.CalledProcessError as e:
      detail = (e.stderr or e.stdout or "").strip ()
      if detail:
         console.err (detail)
      raise

def capture (
   *args: str,
   check: bool = False,
   env: dict [str, str] | None = None,
) -> str:
   """Run Git through the package adapter and return captured stdout."""

   return _run (*args, check=check, env=env).stdout

def succeeds (*args: str) -> bool:
   """Return whether one read-only Git query succeeds."""

   return _run (*args, check=False).returncode == 0

def require ():
   result = _run ("rev-parse", "--git-dir", check=False)

   if result.returncode != 0:
      console.fatal ("Not a git repository")

def require_clean (hint: str = "imp commit first"):
   if not is_clean ():
      console.hint (hint)
      console.fatal ("Uncommitted changes")

def is_repo () -> bool:
   result = _run ("rev-parse", "--git-dir", check=False)
   return result.returncode == 0

def init ():
   _run ("init")

def remote_url (name: str = "origin") -> str:
   result = _run ("remote", "get-url", name, check=False)
   return result.stdout.strip ()

def remote_add (url: str, name: str = "origin"):
   _run ("remote", "add", name, url)

def remote_set_url (url: str, name: str = "origin"):
   _run ("remote", "set-url", name, url)

def stage ():
   _run ("add", "-A")

def add (files: list [str]):
   _run ("add", "--", *files)

def staged_files () -> list [str]:
   result = _run ("diff", "--cached", "--name-only", check=False)
   return [ f.strip () for f in result.stdout.splitlines () if f.strip () ]

def changed_paths (*, staged: bool = False, all_changes: bool = False) -> list [str]:
   """Return exact changed paths with renames expanded into remove and add paths."""

   blocks = []
   if staged or all_changes:
      blocks.append (_run ("diff", "--cached", "--name-only", "--no-renames", "-z", check=False).stdout)
   if all_changes:
      blocks.append (_run ("diff", "--name-only", "--no-renames", "-z", check=False).stdout)
      blocks.append (_run ("ls-files", "--others", "--exclude-standard", "-z", check=False).stdout)

   return sorted ({ path for block in blocks for path in block.split ("\0") if path })

def path_diff (path: str, *, staged: bool) -> str:
   """Return the selected staged or complete diff for one path."""

   if staged:
      return _run ("diff", "--cached", "--binary", "--no-renames", "--", path, check=False).stdout

   tracked = _run ("diff", "HEAD", "--binary", "--no-renames", "--", path, check=False).stdout
   if tracked:
      return tracked

   full = Path (repo_root ()) / path
   if not full.is_file ():
      return ""
   try:
      lines = full.read_text ().splitlines (keepends=True)
   except (OSError, UnicodeDecodeError):
      return f"Binary or unreadable file: {path}"

   return f"--- /dev/null\n+++ b/{path}\n" + "".join (f"+{line}" for line in lines)

def diff (
   staged: bool = False,
   ref: str = "",
   paths: list [str] | None = None,
   stat: bool = False,
   name_only: bool = False,
   color: bool = False,
) -> str:
   args = [ "diff" ]
   if staged:
      args.append ("--cached")
   if stat:
      args.append ("--stat")
   if name_only:
      args.append ("--name-only")
   if color:
      args.append ("--color=always")
   if ref:
      args.append (ref)
   if paths:
      args.extend ([ "--", *paths ])

   result = _run (*args)
   return result.stdout

def diff_range (rev_range: str) -> str:
   result = _run ("diff", rev_range, check=False)
   return result.stdout

def diff_names () -> list [str]:
   blocks = [
      _run ("diff", "--cached", "--name-only", check=False).stdout,
      _run ("diff", "--name-only", check=False).stdout,
      _run ("ls-files", "--others", "--exclude-standard", check=False).stdout,
   ]

   return sorted ({ line.strip () for block in blocks for line in block.splitlines () if line.strip () })

def diff_untracked (
   paths: list [str] | None = None,
   *,
   stat: bool = False,
   name_only: bool = False,
   color: bool = False,
) -> str:
   files = untracked_files (paths)
   if name_only:
      return "\n".join (files)

   patches = []
   for path in files:
      args = [ "diff", "--no-index" ]
      if stat:
         args.append ("--stat")
      if color:
         args.append ("--color=always")
      args.extend ([ "--", "/dev/null", path ])

      result = _run (*args, check=False)
      if result.returncode in { 0, 1 } and result.stdout:
         patches.append (result.stdout.rstrip ())

   return "\n".join (patches)

def diff_file (path: str) -> str:
   result = _run ("diff", "HEAD", "--", path, check=False)
   text = result.stdout
   if not text:
      result = _run ("diff", "--cached", "--", path, check=False)
      text = result.stdout
   return text

def diff_numstat () -> str:
   staged = _run ("diff", "--cached", "--numstat", check=False).stdout.strip ()
   unstaged = _run ("diff", "--numstat", check=False).stdout.strip ()

   return "\n".join (filter (None, [ staged, unstaged ]))

def untracked_files (paths: list [str] | None = None) -> list [str]:
   args = [ "ls-files", "--others", "--exclude-standard", "-z" ]
   if paths:
      args.extend ([ "--", *paths ])

   result = _run (*args, check=False)
   return sorted (path for path in result.stdout.split ("\0") if path)

def branch () -> str:
   result = _run ("branch", "--show-current", check=False)
   return result.stdout.strip ()

def branches_local () -> list [str]:
   result = _run ("branch", "--format=%(refname:short)", check=False)
   return [ b.strip () for b in result.stdout.splitlines () if b.strip () ]

def branches_merged (base: str) -> list [str]:
   result = _run ("branch", "--merged", base, check=False)
   current = branch ()
   merged = []
   for line in result.stdout.splitlines ():
      name = line.removeprefix ("* ").strip ()
      if name and name != base and name != current:
         merged.append (name)
   return merged

def commit (msg: str, amend: bool = False, date: str = ""):
   args = [ "commit", "-m", msg ]
   if amend:
      args.insert (1, "--amend")
   if date:
      args.extend ([ "--date", date ])

   _run (*args, env={ "GIT_COMMITTER_DATE": date } if date else {})

def published (ref: str = "HEAD") -> bool:
   """Return whether a commit is reachable from any remote branch."""

   output = _run ("branch", "-r", "--contains", ref, "--format=%(refname:short)", check=False).stdout
   return bool (output.strip ())

def _count_revs (spec: str) -> int:
   result = _run ("rev-list", "--count", spec, check=False)

   try:
      return int (result.stdout.strip ())
   except ValueError:
      return 0

def commit_count () -> int:
   return _count_revs ("HEAD")

def is_clean () -> bool:
   result = _run ("status", "--porcelain")
   return result.stdout.strip () == ""

def base_branch () -> str:
   result = _run ("symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
   head = result.stdout.strip ().removeprefix ("origin/")
   if head:
      return head

   for name in [ "main", "master" ]:
      result = _run ("rev-parse", "--verify", name, check=False)
      if result.returncode == 0:
         return name

   return "main"

def last_tag () -> str:
   result = _run ("describe", "--tags", "--abbrev=0", check=False)
   return result.stdout.strip ()

def highest_tag (stable: bool = False) -> str:
   result = _run ("tag", "-l", "v*", "--sort=-v:refname", check=False)

   for line in result.stdout.strip ().splitlines ():
      t = line.strip ()
      if not t:
         continue
      if stable and not _SEMVER_TAG_RE.match (t):
         continue
      return t

   return ""

def rc_tags (ver: str) -> list [str]:
   result = _run ("tag", "-l", f"v{ver}-rc.*", "--sort=-v:refname", check=False)
   return [ line.strip () for line in result.stdout.splitlines () if line.strip () ]

def tags (pattern: str = "v*") -> list [str]:
   result = _run ("tag", "-l", pattern, "--sort=-v:refname", check=False)
   return [ line.strip () for line in result.stdout.splitlines () if line.strip () ]

def remote_tags (remote: str = "origin") -> list [str]:
   result = _run ("ls-remote", "--tags", remote, check=False)
   out = []
   for line in result.stdout.splitlines ():
      _, _, ref = line.partition ("refs/tags/")
      # Peeled annotated-tag rows end in ^{}; the bare ref already covers them.
      if ref and not ref.endswith ("^{}"):
         out.append (ref.strip ())
   return out

def tag (name: str, ref: str = ""):
   args = [ "tag", name ]
   if ref:
      args.append (ref)
   _run (*args)

def tag_exists (name: str) -> bool:
   result = _run ("rev-parse", name, check=False)
   return result.returncode == 0

def tag_delete (name: str):
   _run ("tag", "-d", name, check=False)

def push_delete (refs: list [str], remote: str = "origin"):
   """Delete tags (or branches) on the remote in one push. Only pass refs
   known to exist remotely — one missing ref fails the whole push."""
   if not refs:
      return
   _run ("push", remote, "--delete", *refs)

def has_upstream () -> bool:
   result = _run ("rev-parse", "--verify", "@{u}", check=False)
   return result.returncode == 0

def count_ahead () -> int:
   return _count_revs ("@{u}..HEAD")

def count_behind () -> int:
   return _count_revs ("HEAD..@{u}")

def count_between (a: str, b: str) -> int:
   return _count_revs (f"{a}..{b}")

def log_oneline (count: int = 10, rev_range: str = "") -> str:
   args = [ "log", "--oneline" ]
   if rev_range:
      args.append (rev_range)
   else:
      args.extend ([ "-n", str (count) ])
   result = _run (*args, check=False)
   return result.stdout.strip ()

def log_graph (count: int = 20, ref: str = "") -> str:
   args = [
      "log", "--oneline", "--graph",
      "--decorate", "--color=always",
      "-n", str (count),
   ]
   if ref:
      args.append (ref)
   result = _run (*args, check=False)
   return result.stdout.strip ()

def log_subjects (rev_range: str = "", count: int = 0) -> str:
   args = [ "log", "--format=%s" ]
   if rev_range:
      args.append (rev_range)
   elif count > 0:
      args.extend ([ "-n", str (count) ])
   result = _run (*args, check=False)
   return result.stdout.strip ()

def fetch (prune: bool = False, tags: bool = False, remote: str = "", refspec: str = ""):
   args = [ "fetch" ]
   if prune:
      args.append ("--prune")
   if tags:
      args.append ("--tags")
   if remote:
      args.append (remote)
   if refspec:
      args.append (refspec)
   try:
      _run (*args)
   except subprocess.CalledProcessError:
      console.fatal ("Fetch failed")

def rebase (onto: str = "") -> bool:
   args = [ "rebase" ]
   if onto:
      args.append (onto)
   result = _run (*args, check=False)
   return result.returncode == 0

def rebase_continue () -> bool:
   result = _run ("rebase", "--continue", check=False, env={ "GIT_EDITOR": ":" })
   return result.returncode == 0

def rebase_abort ():
   _run ("rebase", "--abort", check=False)

def push (
   force_lease: bool = False,
   set_upstream: bool = False,
   target: str = "",
   ref: str = "",
):
   args = [ "push" ]
   if force_lease:
      args.append ("--force-with-lease")
   if set_upstream:
      args.extend ([ "-u", "origin" ])
      if target:
         args.append (target)
   elif ref:
      args.extend ([ "origin", ref ])
   _run (*args)

def merge (ref: str, no_ff: bool = False) -> bool:
   args = [ "merge" ]
   if no_ff:
      args.append ("--no-ff")
   args.append (ref)
   result = _run (*args, check=False)
   return result.returncode == 0

def merge_preview (ref: str, base: str = "HEAD") -> list [str] | None:
   """Dry-run an integration of <ref>, touching neither the worktree nor the
   index. Returns the conflicting paths, [] when it would land clean, or None
   when git can't say (merge-tree without --write-tree, unrelated histories).

   Output is the merged tree OID, then the conflicted paths, then a blank line
   and informational messages. Exit 0 is clean, 1 is conflicted."""
   result = _run ("merge-tree", "--write-tree", "--name-only", base, ref, check=False)

   if result.returncode == 0:
      return []

   if result.returncode != 1:
      return None

   paths = []

   for line in result.stdout.splitlines () [1:]:
      if not line.strip ():
         break
      paths.append (line)

   return paths

def merge_continue () -> bool:
   result = _run ("commit", "--no-edit", check=False)
   return result.returncode == 0

def merge_abort ():
   _run ("merge", "--abort", check=False)

def is_merged (branch_name: str, into: str) -> bool:
   result = _run ("merge-base", "--is-ancestor", branch_name, into, check=False)
   return result.returncode == 0

def pull ():
   _run ("pull", check=False)

def revert_commit (ref: str, no_commit: bool = False):
   args = [ "revert" ]
   if no_commit:
      args.append ("--no-commit")
   args.append (ref)
   _run (*args)

def revert_abort ():
   _run ("revert", "--abort", check=False)

def cherry_pick (ref: str, no_commit: bool = False):
   args = [ "cherry-pick" ]
   if no_commit:
      args.append ("--no-commit")
   args.append (ref)
   _run (*args)

def cherry_pick_start (ref: str) -> bool:
   result = _run ("cherry-pick", ref, check=False)
   return result.returncode == 0

def cherry_pick_continue () -> bool:
   result = _run ("cherry-pick", "--continue", check=False, env={ "GIT_EDITOR": ":" })
   return result.returncode == 0

def cherry_pick_abort ():
   _run ("cherry-pick", "--abort", check=False)

def update_ref (name: str, ref: str):
   _run ("update-ref", name, ref)

def update_ref_checked (name: str, ref: str, previous: str):
   """Move one ref only when it still names the expected object."""

   expected = previous or null_oid ()
   _run ("update-ref", name, ref, expected)

def delete_ref_checked (name: str, previous: str):
   """Delete one ref only when it still names the expected object."""

   _run ("update-ref", "-d", name, previous)

def delete_ref (name: str):
   _run ("update-ref", "-d", name, check=False)

def log_since (expr: str) -> list [dict [str, str]]:
   result = _run (
      "log", "--since", expr,
      "--format=%H%x09%s", "--reverse",
      check=False,
   )
   entries = []
   for line in result.stdout.strip ().splitlines ():
      parts = line.split ("\t", 1)
      if len (parts) == 2:
         entries.append ({ "hash": parts [0], "subject": parts [1] })
   return entries

def reset (ref: str, soft: bool = False, hard: bool = False):
   args = [ "reset" ]
   if soft:
      args.append ("--soft")
   elif hard:
      args.append ("--hard")
   args.append (ref)
   _run (*args)

def reset_mixed (ref: str):
   """Reset the real index to a ref while preserving worktree files."""

   _run ("reset", "--mixed", ref)

def checkout (ref: str, create: bool = False):
   args = [ "checkout" ]
   if create:
      args.append ("-b")
   args.append (ref)
   _run (*args)

def checkout_side (path: str, side: str):
   _run ("checkout", f"--{side}", "--", path)

def rm (path: str):
   _run ("rm", "--", path)

def show_patch (ref: str) -> str:
   result = _run ("show", "--format=", "--patch", ref, check=False)
   return result.stdout.strip ()

def show_raw (
   ref: str = "HEAD",
   *,
   stat: bool = False,
   name_only: bool = False,
   color: bool = False,
) -> str:
   args = [ "show", "--decorate" ]
   if stat:
      args.append ("--stat")
   if name_only:
      args.append ("--name-only")
   if color:
      args.append ("--color=always")
   args.append (ref)

   result = _run (*args)
   return result.stdout.rstrip ()

def show (ref: str = "HEAD", fmt: str = "", stat: bool = False) -> str:
   args = [ "show" ]
   if fmt:
      args.append (f"--format={fmt}")
   else:
      args.append ("--format=")
   if stat:
      args.append ("--stat")
   args.append (ref)
   result = _run (*args, check=False)
   return result.stdout.strip ()

def status_short () -> str:
   result = _run ("status", "--short")
   return result.stdout.strip ()

def worktree_list () -> str:
   result = _run ("worktree", "list", check=False)
   return result.stdout.strip ()

def worktrees () -> list [dict [str, str]]:
   result = _run ("worktree", "list", "--porcelain", check=False)
   entries: list [dict [str, str]] = []
   current: dict [str, str] = {}

   for line in result.stdout.splitlines ():
      line = line.rstrip ()
      if not line:
         if current:
            entries.append (current)
            current = {}
         continue

      if " " in line:
         key, _, value = line.partition (" ")
         current [key] = value
      else:
         current [line] = ""

   if current:
      entries.append (current)

   return entries

def worktree_add (path: str, branch: str, base: str = ""):
   args = [ "worktree", "add", "-b", branch, path ]
   if base:
      args.append (base)
   _run (*args)

def worktree_add_detached (path: str, ref: str):
   """Create a detached temporary worktree at an exact object."""

   _run ("worktree", "add", "--detach", path, ref)

def run_at (
   path: str,
   *args: str,
   check: bool = True,
   env: dict [str, str] | None = None,
) -> subprocess.CompletedProcess [str]:
   """Run Git in another worktree through Imp's Git adapter."""

   return _run ("-C", path, *args, check=check, env=env)

def clean_at (path: str) -> bool:
   return not run_at (path, "status", "--porcelain=v1", check=False).stdout.strip ()

def reset_at (path: str, ref: str):
   run_at (path, "reset", "--hard", ref)

def commit_at (path: str, message: str):
   run_at (path, "commit", "-m", message)

def tree (ref: str) -> str:
   return rev_parse (f"{ref}^{{tree}}")

def merge_base (left: str, right: str) -> str:
   return _run ("merge-base", left, right).stdout.strip ()

def commit_parents (ref: str) -> list [str]:
   line = _run ("show", "-s", "--format=%P", ref).stdout.strip ()
   return line.split () if line else []

def subject (ref: str) -> str:
   return _run ("show", "-s", "--format=%s", ref).stdout.strip ()

def ref_worktrees (branch_name: str) -> list [str]:
   expected = f"refs/heads/{branch_name}"
   return [entry ["worktree"] for entry in worktrees () if entry.get ("branch") == expected]

def worktree_remove (path: str, force: bool = False):
   args = [ "worktree", "remove" ]
   if force:
      args.append ("--force")
   args.append (path)
   _run (*args)

def worktree_prune ():
   _run ("worktree", "prune", check=False)

def current_ref () -> str:
   """Return the full branch ref currently attached to HEAD."""

   return _run ("symbolic-ref", "-q", "HEAD", check=False).stdout.strip ()

def index_read_tree (index: Path, ref: str):
   """Populate an isolated index from one tree-ish."""

   _run ("read-tree", ref, env={ "GIT_INDEX_FILE": str (index) })

def index_read_empty (index: Path):
   """Populate an isolated index with Git's empty tree."""

   _run ("read-tree", "--empty", env={ "GIT_INDEX_FILE": str (index) })

def index_add_worktree (index: Path, paths: list [str]):
   """Stage worktree paths into an isolated index."""

   _run ("add", "-A", "--", *paths, env={ "GIT_INDEX_FILE": str (index) })

def index_apply (index: Path, patch: str):
   """Apply one patch to an isolated index."""

   environment = { **os.environ, "GIT_INDEX_FILE": str (index) }
   try:
      subprocess.run (
         [ "git", "apply", "--cached", "--whitespace=nowarn", "-" ],
         input=patch,
         capture_output=True,
         text=True,
         check=True,
         timeout=60,
         env=environment,
      )
   except subprocess.CalledProcessError as error:
      detail = (error.stderr or error.stdout or "").strip ()
      raise RuntimeError (f"Cannot apply planned hunk: {detail}") from error

def index_diff (index: Path, path: str = "") -> str:
   """Return the binary-safe HEAD diff represented by an isolated index."""

   args = [ "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", "--no-renames" ]
   if path:
      args.extend ([ "--", path ])
   return capture (*args, env={ "GIT_INDEX_FILE": str (index) })

def index_entry (path: str) -> tuple [str, str] | None:
   """Read the stage-zero mode and object ID for one real-index path."""

   result = _run ("ls-files", "--stage", "-z", "--", path, check=False).stdout
   for entry in result.split ("\0"):
      if not entry or "\t" not in entry:
         continue
      metadata, _, _name = entry.partition ("\t")
      parts = metadata.split ()
      if len (parts) == 3 and parts [2] == "0":
         return parts [0], parts [1]

   return None

def _set_index (path: str, entry: tuple [str, str] | None, environment: dict [str, str] | None = None):
   """Set or remove one path in an index."""

   if entry is None:
      _run ("update-index", "--force-remove", "--", path, check=False, env=environment)
      return

   mode, oid = entry
   _run ("update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}", env=environment)

def index_set (index: Path, path: str, entry: tuple [str, str] | None):
   """Set or remove one path in an isolated index."""

   _set_index (path, entry, { "GIT_INDEX_FILE": str (index) })

def index_set_current (path: str, entry: tuple [str, str] | None):
   """Set or remove one path in the current worktree index."""

   _set_index (path, entry)

def index_path () -> Path:
   """Return the current worktree's real index path."""

   value = Path (capture ("rev-parse", "--git-path", "index", check=True).strip ())
   if not value.is_absolute ():
      value = Path (repo_root ()) / value
   return value.resolve ()

def index_write_tree (index: Path) -> str:
   """Write and return the tree represented by an isolated index."""

   return _run ("write-tree", env={ "GIT_INDEX_FILE": str (index) }).stdout.strip ()

def commit_tree (tree: str, parent: str, message: str) -> str:
   """Create an unattached commit object from an exact tree and parent."""

   args = [ "commit-tree", tree ]
   if parent:
      args.extend ([ "-p", parent ])
   args.extend ([ "-m", message ])
   return _run (*args).stdout.strip ()

def commit_tree_parents (tree_oid: str, parents: list [str], message: str) -> str:
   args = [ "commit-tree", tree_oid ]
   for parent_oid in parents:
      args.extend ([ "-p", parent_oid ])
   args.extend ([ "-m", message ])
   return _run (*args).stdout.strip ()

def merge_tree (left: str, right: str) -> tuple [str, list [str]]:
   """Return a clean merged tree or the exact conflict paths."""

   result = _run ("merge-tree", "--write-tree", "--name-only", left, right, check=False)
   lines = result.stdout.splitlines ()
   if result.returncode == 0 and lines:
      return lines [0].strip (), []
   conflicts = []
   for line in lines [1:]:
      if not line.strip ():
         break
      conflicts.append (line.strip ())
   return "", conflicts

def common_dir () -> str:
   result = _run ("rev-parse", "--git-common-dir", check=False)
   return result.stdout.strip ()

def remote_has_branch (name: str) -> bool:
   result = _run ("ls-remote", "--heads", "origin", name, check=False)
   return name in result.stdout

def remote_exists () -> bool:
   result = _run ("remote", check=False)
   return result.stdout.strip () != ""

def delete_branch (name: str, force: bool = False, remote: bool = False) -> bool:
   if remote:
      result = _run ("push", "origin", "--delete", name, check=False)
      return result.returncode == 0

   flag = "-D" if force else "-d"
   result = _run ("branch", flag, name, check=False)
   return result.returncode == 0

def unstage (files: list [str] | None = None):
   if files:
      if commit_count () > 0:
         _run ("reset", "HEAD", "--", *files, check=False)
      else:
         _run ("rm", "--cached", "--", *files, check=False)
   elif commit_count () > 0:
      _run ("reset", "HEAD", check=False)
   else:
      _run ("rm", "-r", "--cached", ".", check=False)

def repo_root () -> str:
   result = _run ("rev-parse", "--show-toplevel", check=False)
   return result.stdout.strip ()

def repo_name () -> str:
   return Path (repo_root ()).name

def git_dir () -> str:
   result = _run ("rev-parse", "--git-dir", check=False)
   return result.stdout.strip ()

def rev_parse (ref: str) -> str:
   result = _run ("rev-parse", "--verify", ref, check=False)
   return result.stdout.strip () if result.returncode == 0 else ""

def null_oid () -> str:
   """Return the null object ID for this repository's object format."""

   object_format = _run ("rev-parse", "--show-object-format", check=False).stdout.strip ()
   return "0" * (64 if object_format == "sha256" else 40)

def parent (ref: str = "HEAD") -> str:
   """Return the first parent object ID, or empty for a root commit."""

   result = _run ("rev-parse", "--verify", f"{ref}^", check=False)
   return result.stdout.strip () if result.returncode == 0 else ""

def ref_exists (ref: str) -> bool:
   result = _run ("rev-parse", "--verify", "--quiet", ref, check=False)
   return result.returncode == 0

def rev_parse_short (ref: str) -> str:
   result = _run ("rev-parse", "--short", ref, check=False)
   return result.stdout.strip ()

def conflicts () -> list [str]:
   result = _run ("diff", "--name-only", "--diff-filter=U", check=False)
   lines = result.stdout.strip ().splitlines ()
   return [ line.strip () for line in lines if line.strip () ]

def merge_in_progress () -> bool:
   return Path (git_dir (), "MERGE_HEAD").exists ()

def rebase_in_progress () -> bool:
   gd = git_dir ()
   return (
      Path (gd, "rebase-merge").exists ()
      or Path (gd, "rebase-apply").exists ()
   )

def cherry_pick_in_progress () -> bool:
   return Path (git_dir (), "CHERRY_PICK_HEAD").exists ()

def branch_age (name: str) -> str:
   result = _run ("log", "-1", "--format=%cr", name, check=False)
   return result.stdout.strip () or "unknown"

def log_after_date (date: str) -> str:
   result = _run ("log", "--format=%H", "--after", date, "--reverse", check=False)
   lines = result.stdout.strip ().splitlines ()
   return lines [0].strip () if lines else ""

def tag_commit_map () -> dict [str, str]:
   # %(*objectname) dereferences annotated tags to the commit hash;
   # for lightweight tags it's empty, so we fall back to %(objectname)
   result = _run (
      "for-each-ref",
      "--format=%(refname:short) %(*objectname) %(objectname)",
      "--sort=v:refname",
      "refs/tags/v*",
      check=False,
   )
   mapping = {}
   for line in result.stdout.strip ().splitlines ():
      parts = line.strip ().split ()
      if len (parts) == 3:
         # Annotated tag: parts [1] is the dereferenced commit
         mapping [parts [0]] = parts [1] if parts [1] else parts [2]
      elif len (parts) == 2:
         mapping [parts [0]] = parts [1]
   return mapping

def recent_commit_diffs (count: int = 20, since: str = "") -> list [dict [str, str]]:
   if since:
      args = [ "log", "--since", since, "--format=%H%x09%s" ]
   else:
      args = [ "log", "-n", str (count), "--format=%H%x09%s" ]

   result = _run (*args, check=False)
   entries: list [dict [str, str]] = []

   for line in result.stdout.strip ().splitlines ():
      parts = line.split ("\t", 1)
      if len (parts) != 2:
         continue
      h, subject = parts
      patch = show_patch (h)
      entries.append ({ "hash": h, "subject": subject, "diff": patch })

   return entries

def commit_fixup (ref: str):
   _run ("commit", f"--fixup={ref}")

def autosquash_rebase (base_ref: str):
   _run (
      "rebase", "-i", "--autosquash", base_ref,
      env={ "GIT_SEQUENCE_EDITOR": ":" },
   )

def stash_push (msg: str):
   _run ("stash", "push", "-m", msg)

def stash_list_raw () -> list [dict [str, str]]:
   result = _run ("stash", "list", "--format=%gd%x09%gs%x09%cr", check=False)
   entries: list [dict [str, str]] = []
   for line in result.stdout.strip ().splitlines ():
      parts = line.split ("\t", 2)
      if len (parts) == 3:
         entries.append ({ "ref": parts [0], "subject": parts [1], "age": parts [2] })
   return entries

def stash_show (idx: int = 0, patch: bool = False) -> str:
   ref = f"stash@{{{idx}}}"
   args = [ "stash", "show" ]
   if patch:
      args.append ("-p")
   else:
      args.append ("--numstat")
   args.append (ref)
   result = _run (*args, check=False)
   return result.stdout

def stash_pop (idx: int = 0):
   _run ("stash", "pop", f"stash@{{{idx}}}")

def stash_drop (idx: int = 0):
   _run ("stash", "drop", f"stash@{{{idx}}}")

def reflog (since: str = "") -> list [dict [str, str]]:
   args = [ "reflog", "show", "--all", "--format=%H%x09%gD%x09%gs%x09%cr" ]
   if since:
      args.extend ([ "--since", since ])

   result = _run (*args, check=False)
   entries: list [dict [str, str]] = []
   for line in result.stdout.strip ().splitlines ():
      parts = line.split ("\t", 3)
      if len (parts) == 4:
         entries.append ({
            "hash": parts [0],
            "ref": parts [1],
            "message": parts [2],
            "age": parts [3],
         })
   return entries

def dangling_commits () -> list [str]:
   result = _run ("fsck", "--no-reflogs", "--lost-found", check=False)
   commits: list [str] = []
   for line in result.stdout.splitlines () + result.stderr.splitlines ():
      line = line.strip ()
      if line.startswith ("dangling commit "):
         commits.append (line.split () [-1])
   return commits

def show_oneline (ref: str) -> str:
   result = _run ("log", "-1", "--format=%h %s", ref, check=False)
   return result.stdout.strip ()

def log_history (path: str = "", count: int = 20, color: bool = False) -> str:
   args = [
      "log",
      "--decorate",
      "--date=short",
      "--format=%C(auto)%h%Creset %ad %C(auto)%d%Creset %s %C(dim)<%an>%Creset",
      "-n",
      str (count),
   ]
   if color:
      args.append ("--color=always")
   if path:
      args.extend ([ "--follow", "--", path ])

   result = _run (*args, check=False)
   return result.stdout.rstrip ()

def log_history_patches (path: str, count: int = 10) -> str:
   args = [ "log", "-p", "--format=commit %h: %s", "-n", str (count), "--", path ]
   result = _run (*args, check=False)
   return result.stdout.rstrip ()

def grep (
   pattern: str,
   paths: list [str] | None = None,
   *,
   ignore_case: bool = False,
   line_number: bool = True,
   extended: bool = False,
) -> tuple [str, int]:
   args = [ "grep" ]
   if extended:
      args.append ("--extended-regexp")
   if ignore_case:
      args.append ("--ignore-case")
   if line_number:
      args.append ("--line-number")
   args.extend ([ "-e", pattern ])
   if paths:
      args.extend ([ "--", *paths ])

   result = _run (*args, check=False)
   return result.stdout.rstrip (), result.returncode

def restore (
   paths: list [str],
   *,
   staged: bool = False,
   worktree: bool = False,
   source: str = "",
):
   args = [ "restore" ]
   if staged:
      args.append ("--staged")
   if worktree:
      args.append ("--worktree")
   if source:
      args.extend ([ "--source", source ])
   args.extend ([ "--", *paths ])
   _run (*args)

def show_age (ref: str) -> str:
   result = _run ("log", "-1", "--format=%cr", ref, check=False)
   return result.stdout.strip ()

def show_stat (ref: str) -> str:
   result = _run ("show", "--stat", "--format=", ref, check=False)
   return result.stdout.strip ()

def user_email () -> str:
   result = _run ("config", "--get", "user.email", check=False)
   return result.stdout.strip ()

def log_by_author (author: str, since: str = "") -> list [dict [str, str]]:
   args = [ "log", "--author", author, "--format=%H\t%ai\t%s", "--reverse" ]
   if since:
      args.extend ([ "--since", since ])
   result = _run (*args, check=False)
   entries: list [dict [str, str]] = []
   for line in result.stdout.strip ().splitlines ():
      parts = line.split ("\t", 2)
      if len (parts) == 3:
         entries.append ({
            "hash": parts [0],
            "subject": parts [2],
            "date": parts [1].split () [0],
         })
   return entries

def log_full (since: str = "", until: str = "") -> list [dict [str, str]]:
   args = [ "log", "--format=%H\t%ai\t%s", "--reverse" ]
   if since and until:
      args.append (f"{since}..{until}")
   elif since:
      args.append (f"{since}..HEAD")
   result = _run (*args, check=False)
   entries = []
   for line in result.stdout.strip ().splitlines ():
      parts = line.split ("\t", 2)
      if len (parts) == 3:
         entries.append ({
            "hash": parts [0],
            "subject": parts [2],
            "date": parts [1].split () [0],
         })
   return entries
