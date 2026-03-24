from imp import console


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
   console.out.print ('  imp branch "add auth"                     [muted]# create branch from description[/muted]')
   console.out.print ("  imp branch                                [muted]# switch between branches[/muted]")
   console.out.print ("  imp fix 42                                [muted]# or from a GitHub issue[/muted]")
   console.out.print ()

   console.out.print ("[bold]While working[/bold]")
   console.out.print ("  imp review                                [muted]# AI code review[/muted]")
   console.out.print ("  imp commit -a                             [muted]# stage all + AI commit message[/muted]")
   console.out.print ("  imp split                                 [muted]# group changes into logical commits[/muted]")
   console.out.print ("  imp amend                                 [muted]# fix last commit[/muted]")
   console.out.print ("  imp undo [N]                              [muted]# undo last N commits[/muted]")
   console.out.print ("  imp revert <hash>                         [muted]# safely undo a pushed commit[/muted]")
   console.out.print ()

   console.out.print ("[bold]Staying in sync[/bold]")
   console.out.print ("  imp sync                                  [muted]# pull, rebase, push[/muted]")
   console.out.print ("  imp status                                [muted]# repo overview[/muted]")
   console.out.print ("  imp log                                   [muted]# pretty commit graph[/muted]")
   console.out.print ()

   console.out.print ("[bold]Shipping[/bold]")
   console.out.print ("  imp pr                                    [muted]# create pull request[/muted]")
   console.out.print ("  imp done                                  [muted]# clean up after PR merge[/muted]")
   console.out.print ("  imp clean                                 [muted]# delete merged branches[/muted]")
   console.out.print ("  imp release                               [muted]# squash + changelog + tag + push[/muted]")
   console.out.print ("  imp ship [level]                           [muted]# commit + release, no prompts[/muted]")
   console.out.print ()

   console.out.print ("[bold]Setup[/bold]")
   console.out.print ("  imp config                                [muted]# configure AI provider and models[/muted]")
   console.out.print ("  imp doctor                                [muted]# verify tools and connection[/muted]")
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
