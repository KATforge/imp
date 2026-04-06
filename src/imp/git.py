import os
import subprocess
from pathlib import Path

from imp import console


def _run (*args: str, check: bool = True, timeout: int = 60, env: dict [str, str] | None = None) -> subprocess.CompletedProcess [str]:
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
   except subprocess.CalledProcessError:
      raise


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


def diff (staged: bool = False) -> str:
   args = [ "diff" ]
   if staged:
      args.append ("--cached")

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

   return sorted ({l.strip () for b in blocks for l in b.splitlines () if l.strip ()})


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
      if stable and "-" in t [1:]:
         continue
      return t

   return ""


def rc_tags (ver: str) -> list [str]:
   result = _run ("tag", "-l", f"v{ver}-rc.*", "--sort=-v:refname", check=False)
   return [ l.strip () for l in result.stdout.splitlines () if l.strip () ]


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


def fetch (prune: bool = False):
   args = [ "fetch" ]
   if prune:
      args.append ("--prune")
   _run (*args, check=False)


def rebase () -> bool:
   result = _run ("rebase", check=False)
   return result.returncode == 0


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


def reset (ref: str, soft: bool = False, hard: bool = False):
   args = [ "reset" ]
   if soft:
      args.append ("--soft")
   elif hard:
      args.append ("--hard")
   args.append (ref)
   _run (*args)


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
   result = _run ("rev-parse", ref, check=False)
   return result.stdout.strip ()


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
