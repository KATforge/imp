from imp_git import console


def _command (value: str, detail: str):
   console.out.print (f"  {value:<43} [muted]# {detail}[/muted]")


def help ():
   """Show workflow guide and common commands.

   Prints a quick-reference of all imp commands organized by workflow
   phase (starting, working, syncing, shipping) with common flow
   examples for solo, feature-branch, and hotfix patterns.
   """

   console.header ("imp workflow")

   console.out.print ("imp wraps git with AI. You commit locally as you work,")
   console.out.print ("then squash everything into a clean release when ready.")
   console.out.print ()

   console.divider ()
   console.out.print ()

   console.out.print ("[bold]Starting a feature[/bold]")
   _command ('imp branch "add auth"', "create branch from description")
   _command ("imp branch", "switch between branches")
   _command ("imp fix 42", "or from a GitHub issue")
   console.out.print ()

   console.out.print ("[bold]While working[/bold]")
   _command ("imp add [paths]", "stage directly or use AI groups with no paths")
   _command ("imp diff [--no-ai]", "tracked + untracked changes, then AI insight")
   _command ("imp grep <query> [--ai]", "search tracked content")
   _command ("imp review", "AI code review")
   _command ("imp commit -a", "stage all + AI commit message")
   _command ("imp split", "group changes into logical commits")
   _command ("imp amend", "fix last commit")
   _command ("imp undo [N]", "undo last N commits")
   _command ("imp revert <hash>", "safely undo a pushed commit")
   _command ("imp restore <paths>", "preview restore + save recovery patch")
   console.out.print ()

   console.out.print ("[bold]Staying in sync[/bold]")
   _command ("imp pull", "fetch + integrate upstream, AI-resolve conflicts")
   _command ("imp sync", "pull, rebase, push")
   _command ("imp merge <branch>", "merge a branch in, AI-resolve conflicts")
   _command ("imp cherry-pick <hash>", "preview + apply, AI-resolve conflicts")
   _command ("imp resolve", "resume an in-progress merge or rebase")
   _command ("imp status", "repo overview")
   _command ("imp log", "pretty commit graph")
   _command ("imp history [path] [-e]", "repository or file narrative")
   _command ("imp show [hash] [-e]", "show + optionally explain a commit")
   _command ('imp bisect BAD GOOD --run "cmd"', "find a regression")
   console.out.print ()

   console.out.print ("[bold]Shipping[/bold]")
   _command ("imp pr [--into <branch>]", "create pull request")
   _command ("imp done", "finish a feature branch, then delete it")
   _command ("imp clean", "delete merged branches")
   _command ("imp tag [--patch|--minor|--major]", "bump tag + changelog + push")
   _command ("imp release [--patch|--minor|--major]", "squash + changelog + tag + push")
   _command ("imp collapse <version> --since <floor>", "fold releases into one tag")
   _command ("imp ship [--patch|--minor|--major]", "commit + release, no prompts")
   _command ("imp fleet [path]", "ship every dirty repo in a directory")
   _command ("imp version [--sync]", "check/fix manifest drift vs tag")
   console.out.print ()

   console.out.print ("[bold]Setup[/bold]")
   _command ("imp init [url]", "bootstrap a Git repository")
   _command ("imp setup", "configure this repo's docs and changelog")
   _command ("imp config", "configure AI provider and models")
   _command ("imp docs", "sync prose docs against recent commits")
   _command ("imp doctor", "verify tools and connection")
   _command ("imp update", "update imp itself")
   _command ("imp <git-command> [args]", "pass unsupported syntax to Git")
   console.out.print ()

   console.divider ()
   console.out.print ()

   console.out.print ("[bold]Commit format[/bold] [muted](Conventional Commits)[/muted]")
   console.out.print ()
   console.out.print ("  [muted]type: message[/muted]")
   console.out.print ("  [muted]type(scope): message[/muted]")
   console.out.print ("  [muted]type!: message                          breaking change[/muted]")
   console.out.print ()
   console.out.print ("  feat        [muted]new feature[/muted]        build    [muted]build system, deps[/muted]")
   console.out.print ("  fix         [muted]bug fix[/muted]            chore    [muted]maintenance, config[/muted]")
   console.out.print ("  refactor    [muted]restructure code[/muted]   docs     [muted]documentation[/muted]")
   console.out.print ("  test        [muted]add/update tests[/muted]   style    [muted]formatting, whitespace[/muted]")
   console.out.print ("  perf        [muted]performance[/muted]        ci       [muted]CI/CD pipelines[/muted]")
   console.out.print ()
   console.out.print ("  [muted]Tickets go after the colon:[/muted]  fix: IMP-123 resolve timeout")
   console.out.print ("  [muted]Scopes are optional:[/muted]         refactor(auth): simplify flow")
   console.out.print ()
   console.out.print ("  [muted]All lowercase after colon (except ticket IDs)[/muted]")
   console.out.print ("  [muted]Imperative mood (add, not added). Max 72 chars, no period.[/muted]")
   console.out.print ()

   console.divider ()
   console.out.print ()

   console.out.print ("[bold]AI whisper[/bold]")
   console.out.print ()
   console.out.print ('  [muted]Any AI command accepts[/muted] --whisper / -w [muted]to hint the AI:[/muted]')
   console.out.print ()
   console.out.print ('  imp commit -a -w "use IMP-99999 as ticket"')
   console.out.print ('  imp branch "auth flow" -w "use feat/ prefix"')
   console.out.print ('  imp review -w "focus on error handling"')
   console.out.print ()

   console.divider ()
   console.out.print ()

   console.out.print ("[bold]Common flows[/bold]")
   console.out.print ()
   console.muted ("Solo (trunk-based):")
   console.out.print ("  imp commit -a  →  imp commit -a  →  imp release")
   console.out.print ()
   console.muted ("Feature branch:")
   console.out.print ("  imp branch  →  imp commit -a  →  imp pr  →  imp done")
   console.out.print ()
   console.muted ("Hotfix:")
   console.out.print ("  imp fix 42  →  imp commit -a  →  imp pr  →  imp done")
   console.out.print ()
