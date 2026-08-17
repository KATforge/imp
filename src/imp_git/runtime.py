from dataclasses import dataclass


@dataclass
class Options:
   """Invocation-wide options shared by native Imp commands."""

   actor_id: str = ""
   command: str = ""
   dry_run: bool = False
   json: bool = False
   no_input: bool = False
   repo: str = ""
   yes: bool = False


options = Options ()


def reset ():
   """Reset invocation options between embedded or test invocations."""

   global options
   options = Options ()


def configure (
   *,
   actor_id: str = "",
   command: str = "",
   dry_run: bool = False,
   json: bool = False,
   no_input: bool = False,
   repo: str = "",
   yes: bool = False,
):
   """Set options for the current CLI invocation."""

   global options
   options = Options (
      actor_id=actor_id,
      command=command,
      dry_run=dry_run,
      json=json,
      no_input=no_input,
      repo=repo,
      yes=yes,
   )
