import os
from pathlib import Path

import typer

from imp import console, git, repo

_SKIP_TYPES = [ "chore", "release", "merge", "docs", "test", "style", "ci", "build" ]

def _looks_like_url (arg: str) -> bool:
   return bool (arg) and ("://" in arg or arg.startswith ("git@") or arg.endswith (".git"))

def _detect_docs (root: Path) -> str:
   """Guess a sibling docs repo so the path prompt has a sensible default."""
   for up in ( root.parent, root.parent.parent ):
      if not up or not up.is_dir ():
         continue
      for d in sorted (up.glob ("docs*")):
         if not d.is_dir ():
            continue
         content = d / "content"
         target = content if content.is_dir () else d
         return os.path.relpath (target, root)
   return ""

def _configure_docs (cfg: dict, root: Path):
   default_path = cfg.get ("docs:path", "") or _detect_docs (root)
   docs_path = console.prompt ("Docs path (blank to skip docs sync)", default_path).strip ()

   if not docs_path:
      for k in ( "docs:include", "docs:mode", "docs:path", "docs:release" ):
         cfg.pop (k, None)
      console.muted ("Docs sync disabled")
      return

   cfg ["docs:path"] = docs_path

   abs_root = (root / docs_path).resolve ()
   subdirs = []
   if abs_root.is_dir ():
      subdirs = sorted (d.name for d in abs_root.iterdir () if d.is_dir () and not d.name.startswith ("."))

   if subdirs:
      chosen = console.check (
         "Scope to subfolders (none = all)",
         subdirs,
         cfg.get ("docs:include", []),
      )
      if chosen:
         cfg ["docs:include"] = chosen
      else:
         cfg.pop ("docs:include", None)

   cfg ["docs:mode"] = console.choose ("Edit mode", [ "reconcile", "additive" ])
   cfg ["docs:release"] = console.choose ("Run docs sync on release?", [ "No", "Yes" ]) == "Yes"

def setup (
   arg: str = typer.Argument ("", help="(unused; guards against the old 'imp setup <url>')"),
):
   """Configure this repo's .imp file: docs sync and changelog rules.

   Interactive. Points imp at the project's documentation, sets how aggressive
   documentation sync may be, and picks which commit types the changelog skips.
   Writes a committed .imp at the repo root. To bootstrap a git repo instead,
   use imp init.
   """

   # imp setup used to bootstrap a repo from a URL — that is imp init now.
   if _looks_like_url (arg):
      console.hint (f"imp init {arg}")
      console.fatal ("imp setup now configures .imp; use imp init to bootstrap a repo")

   git.require ()

   console.header ("Setup")

   cfg = dict (repo.load ())
   p = repo.path ()
   root = Path (git.repo_root ())

   console.muted (f"Config: {p}")
   console.out.print ()

   _configure_docs (cfg, root)

   skip = console.check (
      "Skip commit types in changelog",
      _SKIP_TYPES,
      cfg.get ("changelog:skip", [ "chore", "release", "merge" ]),
   )
   if skip:
      cfg ["changelog:skip"] = skip
   else:
      cfg.pop ("changelog:skip", None)

   repo.save (cfg)

   console.out.print ()
   console.success (f"Wrote {p.name}")
   for k in sorted (cfg):
      console.muted (f"  {k}: {cfg [k]}")
   console.hint ("imp docs to try documentation sync")
