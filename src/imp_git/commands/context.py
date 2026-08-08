from typing import Annotated

import typer

from imp_git import console, features, identity, repo, result, runtime, state


def _resolve (name: str) -> dict:
   try:
      return features.resolve (name, title="Select feature context")
   except state.StateError as error:
      console.fatal (str (error))


def _markdown (data: dict) -> str:
   checks = data ["checks"]
   lines = [
      "# Imp Workstream",
      "",
      f"- Feature: `{data ['feature_id']}`",
      f"- Actor: `{data ['actor_id']}`",
      f"- Writable root: `{data ['path']}`",
      f"- Branch: `{data ['branch']}`",
      f"- Target: `{data ['target']}`",
   ]
   if data ["change_id"]:
      lines.append (f"- Change: `{data ['change_id']}`")
   if data ["task"]:
      lines.append (f"- Intent: {data ['task']}")
   lines.extend ([
      "",
      "Use Imp for every Git command.",
      "Create local commits only after explicit approval.",
      "Do not push, integrate, ship, or mark human review without separate approval.",
      "Do not create AGENTS.md, CLAUDE.md, CODEX.md, or provider instruction files.",
   ])
   if checks:
      lines.extend ([ "", "Configured checks:" ])
      lines.extend (f"- `{' '.join (check ['run'])}`" for check in checks)
   return "\n".join (lines).rstrip () + "\n"


def context (
   feature: Annotated [str, typer.Argument (help="Managed feature name")] = "",
   markdown: Annotated [bool, typer.Option ("--markdown", help="Emit adapter-neutral Markdown")] = False,
   json_output: Annotated [bool, typer.Option ("--json", help="Emit a versioned JSON result")] = False,
   actor_id: Annotated [str, typer.Option ("--actor-id", help="Advanced actor override")] = "",
):
   """Claim a feature and render adapter-neutral session context."""

   actor = identity.actor (actor_id)
   managed = _resolve (feature)
   try:
      claim = features.claim (managed, actor)
   except state.StateError as error:
      console.fatal (str (error))
   checks = repo.get ("check:commands", []) or []
   data = {
      "actor_id": actor,
      "branch": managed ["branch"],
      "change_id": managed.get ("change_id") or None,
      "checks": checks,
      "claim": claim,
      "feature_id": managed ["feature_id"],
      "name": managed ["name"],
      "path": managed ["path"],
      "target": managed ["target"],
      "task": managed.get ("task") or None,
   }
   text = _markdown (data)
   context_path = state.root () / "contexts" / f"{identity.key (str (managed ['feature_id']))}.md"
   context_path.parent.mkdir (parents=True, exist_ok=True)
   temporary = context_path.with_name (f".{context_path.name}.tmp")
   temporary.write_text (text)
   temporary.chmod (0o600)
   temporary.replace (context_path)
   data ["context"] = str (context_path)
   if json_output or runtime.options.json:
      result.emit ("imp.context.v1", "imp context", data, json_output=True)
   elif markdown:
      console.out.print (text, markup=False)
   else:
      console.out.print (text, markup=False)
      console.muted (f"Context: {context_path}")
   return data
