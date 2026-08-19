import re

from imp_git import git

_SENTENCE = re.compile (r"(?<=[.!?])\s")


def cap () -> int:
   return 72


def bullet (text: str, width: int) -> str:
   """Reduce one commit subject to a single short line.

   A summary is scanned, not read, so each line keeps its first clause only and
   stops at the subject cap on a word boundary rather than mid-word.
   """

   first = _SENTENCE.split (" ".join (text.split ()), 1) [0].rstrip (".!? ")
   if len (first) <= width:
      return first
   clipped = first [:width].rsplit (" ", 1) [0]

   return f"{clipped or first [:width]}…"


def bullets (base: str, head: str) -> list [str]:
   """Summarise one range as short lines, oldest work first and duplicates dropped."""

   width = cap ()
   values: list [str] = []
   for line in reversed (git.log_oneline (rev_range=f"{base}..{head}").splitlines ()):
      value = bullet (line.split (" ", 1) [-1], width)
      if value and value not in values:
         values.append (value)
   if not values:
      values = [ bullet (git.subject (head) or head, width) ]

   return values


def body (base: str, head: str) -> str:
   """Render one range as a bullet list."""

   return "\n".join (f"- {value}" for value in bullets (base, head)) + "\n"
