import json
import os
import subprocess
import urllib.request

import typer

from imp import console

_PROVIDER = os.environ.get ("IMP_AI_PROVIDER", "claude")
_MODEL_FAST = os.environ.get ("IMP_AI_MODEL_FAST", "haiku")
_MODEL_SMART = os.environ.get ("IMP_AI_MODEL_SMART", "sonnet")

MAX_DIFF_LINES = 2000


def _claude (prompt: str, model: str) -> str:
   result = subprocess.run (
      [
         "claude", "-p",
         "--model", model,
         "--max-turns", "1",
         "--tools", "",
      ],
      input=prompt,
      capture_output=True,
      text=True,
      timeout=120,
   )

   if result.returncode != 0:
      console.err ("claude CLI failed")
      raise typer.Exit (1)

   return result.stdout


def _ollama (prompt: str, model: str) -> str:
   payload = json.dumps ({
      "model": model,
      "prompt": prompt,
      "stream": False,
   }).encode ()

   req = urllib.request.Request (
      "http://localhost:11434/api/generate",
      data=payload,
      headers={"Content-Type": "application/json"},
   )

   try:
      with urllib.request.urlopen (req, timeout=30) as resp:
         body = json.loads (resp.read ())
         return body.get ("response", "")
   except Exception:
      console.err ("ollama request failed")
      raise typer.Exit (1)


def _call (prompt: str, model: str) -> str:
   if _PROVIDER == "claude":
      return _claude (prompt, model)
   elif _PROVIDER == "ollama":
      return _ollama (prompt, model)
   else:
      console.err (f"Unknown AI provider: {_PROVIDER}")
      raise typer.Exit (1)


def fast (prompt: str) -> str:
   result = console.spin ("Generating...", _call, prompt, _MODEL_FAST)
   if not result or not result.strip ():
      console.err ("Empty response from AI")
      raise typer.Exit (1)

   return result


def smart (prompt: str) -> str:
   result = console.spin ("Thinking...", _call, prompt, _MODEL_SMART)
   if not result or not result.strip ():
      console.err ("Empty response from AI")
      raise typer.Exit (1)

   return result


def sanitize (text: str) -> str:
   return text.replace ("\n", "").strip ()


def truncate (text: str, max_lines: int = MAX_DIFF_LINES) -> str:
   lines = text.splitlines ()
   if len (lines) <= max_lines:
      return text
   return "\n".join (lines [:max_lines])


def commit_message (prompt: str) -> str:
   from imp import validate

   msg = fast (prompt)
   msg = sanitize (msg)

   if not validate.commit (msg):
      console.warn ("Retrying (invalid format)...")
      msg = fast (prompt)
      msg = sanitize (msg)

      if not validate.commit (msg):
         console.err ("AI output not in Conventional Commits format")
         console.muted (msg)
         raise typer.Exit (1)

   return msg
