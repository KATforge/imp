import typer

from imp_git import ai, console, git, prompts


def grep (
   query: str = typer.Argument (..., help="Pattern, or natural-language question with --ai"),
   paths: list [str] | None = typer.Argument (None, help="Paths to search"),
   ai_search: bool = typer.Option (False, "--ai", help="Translate a question into a search pattern"),
   explain: bool = typer.Option (False, "--explain", "-e", help="Explain the matches with AI"),
   ignore_case: bool = typer.Option (False, "--ignore-case", "-i", help="Ignore case"),
):
   """Search tracked content exactly or from a natural-language question."""

   git.require ()
   pattern = query

   if ai_search:
      pattern = ai.oneline (ai.strip_fences (ai.fast (prompts.grep_pattern (query))))
      if not pattern:
         console.fatal ("AI returned an empty search pattern")
      console.muted (f"Pattern: {pattern}")

   matches, code = git.grep (
      pattern,
      paths or [],
      ignore_case=ignore_case,
      extended=ai_search,
   )

   if code not in { 0, 1 }:
      console.fatal ("Search failed")
   if not matches:
      console.muted ("No matches")
      raise typer.Exit (1)

   console.out.print (matches, markup=False, highlight=False)
   if not explain:
      return

   summary = console.spin (
      "Explaining matches...",
      ai.smart,
      prompts.grep_summary (query, pattern, ai.truncate (matches)),
   )

   console.out.print ()
   console.label ("AI answer")
   console.md (summary)
