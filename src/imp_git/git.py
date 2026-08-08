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
   """Run Git through the package boundary and return captured stdout."""

   return _run (*args, check=check, env=env).stdout

def succeeds (*args: str) -> bool:
   """Return whether one read-only Git query succeeds."""

   return _run (*args, check=False).returncode == 0

def require ():
   result = _run ("rev-parse", "--git-dir", check=False)

   if result.returncode != 0:
      console.fatal ("Not a git repository")

def remote_url (name: str = "origin") -> str:
   result = _run ("remote", "get-url", name, check=False)
   return result.stdout.strip ()

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
   """Return local branch names without decoration."""

   result = _run ("for-each-ref", "--format=%(refname:short)", "refs/heads", check=False)
   return [line for line in result.stdout.splitlines () if line]

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

def has_upstream () -> bool:
   result = _run ("rev-parse", "--verify", "@{u}", check=False)
   return result.returncode == 0

def count_ahead () -> int:
   return _count_revs ("@{u}..HEAD")

def count_behind () -> int:
   return _count_revs ("HEAD..@{u}")

def log_oneline (count: int = 10, rev_range: str = "") -> str:
   args = [ "log", "--oneline" ]
   if rev_range:
      args.append (rev_range)
   else:
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

def is_merged (branch_name: str, into: str) -> bool:
   result = _run ("merge-base", "--is-ancestor", branch_name, into, check=False)
   return result.returncode == 0

def update_ref_checked (name: str, ref: str, previous: str):
   """Move one ref only when it still names the expected object."""

   expected = previous or null_oid ()
   _run ("update-ref", name, ref, expected)

def delete_ref_checked (name: str, previous: str):
   """Delete one ref only when it still names the expected object."""

   _run ("update-ref", "-d", name, previous)

def reset_mixed (ref: str):
   """Reset the real index to a ref while preserving worktree files."""

   _run ("reset", "--mixed", ref)

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
   """Run Git in another worktree through Imp's Git boundary."""

   return _run ("-C", path, *args, check=check, env=env)

def clean_at (path: str) -> bool:
   return not run_at (path, "status", "--porcelain=v1", check=False).stdout.strip ()

def reset_at (path: str, ref: str):
   run_at (path, "reset", "--hard", ref)

def tree (ref: str) -> str:
   return rev_parse (f"{ref}^{{tree}}")

def merge_base (left: str, right: str) -> str:
   return _run ("merge-base", left, right).stdout.strip ()

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
      raise RuntimeError (f"Cannot apply planned change: {detail}") from error

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

def repo_root () -> str:
   result = _run ("rev-parse", "--show-toplevel", check=False)
   return result.stdout.strip ()

def repo_name () -> str:
   return Path (repo_root ()).name

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

def commit_fixup (ref: str):
   _run ("commit", f"--fixup={ref}")
