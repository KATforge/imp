import subprocess

import typer

from imp import console


def _run (*args: str, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess [str]:
   try:
      return subprocess.run (
         [ "git", *args ],
         capture_output=True,
         text=True,
         check=check,
         timeout=timeout,
      )
   except subprocess.TimeoutExpired:
      console.err (f"git {args [0]} timed out")
      raise typer.Exit (1) from None


def require ():
   result = _run ("rev-parse", "--git-dir", check=False)
   if result.returncode != 0:
      console.err ("Not a git repository")
      raise typer.Exit (1)


def require_clean (hint: str = "imp commit first"):
   if not is_clean ():
      console.err ("Uncommitted changes")
      console.hint (hint)
      raise typer.Exit (1)


def stage (all: bool = False):
   if all:
      _run ("add", "-A")


def add (files: list [str]):
   _run ("add", "--", *files)


def diff (staged: bool = False) -> str:
   args = [ "diff" ]
   if staged:
      args.append ("--cached")

   result = _run (*args)
   return result.stdout


def diff_range (rev_range: str, max_lines: int = 0) -> str:
   args = [ "diff", rev_range ]
   result = _run (*args, check=False)
   text = result.stdout
   if max_lines > 0:
      lines = text.splitlines ()
      text = "\n".join (lines [:max_lines])
   return text


def diff_names () -> list [str]:
   staged = _run ("diff", "--cached", "--name-only", check=False).stdout.strip ()
   unstaged = _run ("diff", "--name-only", check=False).stdout.strip ()
   untracked = _run (
      "ls-files", "--others", "--exclude-standard",
      check=False,
   ).stdout.strip ()

   names = set ()
   for block in [ staged, unstaged, untracked ]:
      for line in block.splitlines ():
         line = line.strip ()
         if line:
            names.add (line)

   return sorted (names)


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
   combined = ""
   if staged:
      combined += staged + "\n"
   if unstaged:
      combined += unstaged
   return combined.strip ()


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


def commit (msg: str, amend: bool = False):
   args = [ "commit", "-m", msg ]
   if amend:
      args.insert (1, "--amend")

   _run (*args)


def commit_count () -> int:
   result = _run ("rev-list", "--count", "HEAD", check=False)
   try:
      return int (result.stdout.strip ())
   except ValueError:
      return 0


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


def highest_tag () -> str:
   result = _run ("tag", "-l", "v*", "--sort=-v:refname", check=False)
   lines = result.stdout.strip ().splitlines ()
   return lines [0].strip () if lines and lines [0].strip () else ""


def tag (name: str):
   _run ("tag", name)


def tag_exists (name: str) -> bool:
   result = _run ("rev-parse", name, check=False)
   return result.returncode == 0


def tag_delete (name: str):
   _run ("tag", "-d", name, check=False)


def has_upstream () -> bool:
   result = _run ("rev-parse", "--verify", "@{u}", check=False)
   return result.returncode == 0


def count_ahead () -> int:
   result = _run ("rev-list", "--count", "@{u}..HEAD", check=False)
   try:
      return int (result.stdout.strip ())
   except ValueError:
      return 0


def count_behind () -> int:
   result = _run ("rev-list", "--count", "HEAD..@{u}", check=False)
   try:
      return int (result.stdout.strip ())
   except ValueError:
      return 0


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
   else:
      flag = "-D" if force else "-d"
      result = _run ("branch", flag, name, check=False)
      return result.returncode == 0


def unstage ():
   _run ("reset", "HEAD", check=False)


def repo_root () -> str:
   result = _run ("rev-parse", "--show-toplevel", check=False)
   return result.stdout.strip ()


def repo_name () -> str:
   from pathlib import Path
   return Path (repo_root ()).name


def rev_parse (ref: str) -> str:
   result = _run ("rev-parse", ref, check=False)
   return result.stdout.strip ()


def rev_parse_short (ref: str) -> str:
   result = _run ("rev-parse", "--short", ref, check=False)
   return result.stdout.strip ()


def branch_age (name: str) -> str:
   result = _run ("log", "-1", "--format=%cr", name, check=False)
   return result.stdout.strip () or "unknown"
