import json
import subprocess
import urllib.error
import urllib.request

import typer

from imp import config, console

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
      with urllib.request.urlopen (req) as resp:
         body = json.loads (resp.read ())
         return body.get ("response", "")
   except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
      console.err (f"ollama request failed: {e}")
      raise typer.Exit (1) from None


def _call (prompt: str, model: str) -> str:
   provider = config.get ("provider")
   if provider == "claude":
      return _claude (prompt, model)
   elif provider == "ollama":
      return _ollama (prompt, model)
   else:
      console.err (f"Unknown AI provider: {provider}")
      raise typer.Exit (1)


def fast (prompt: str, spin: bool = True) -> str:
   model = config.get ("model:fast")
   if spin:
      result = console.spin ("Thinking...", _call, prompt, model)
   else:
      result = _call (prompt, model)
   if not result or not result.strip ():
      console.err ("Empty response from AI")
      raise typer.Exit (1)

   return result


def smart (prompt: str, spin: bool = True) -> str:
   model = config.get ("model:smart")
   if spin:
      result = console.spin ("Thinking...", _call, prompt, model)
   else:
      result = _call (prompt, model)
   if not result or not result.strip ():
      console.err ("Empty response from AI")
      raise typer.Exit (1)

   return result


def ping () -> bool:
   try:
      model = config.get ("model:fast")
      result = _call ("Reply with OK", model)
      return bool (result and result.strip ())
   except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
      return False
   except SystemExit:
      return False


def oneline (text: str) -> str:
   return text.replace ("\n", "").strip ()


def truncate (text: str, max_lines: int = MAX_DIFF_LINES) -> str:
   lines = text.splitlines ()
   if len (lines) <= max_lines:
      return text
   return "\n".join (lines [:max_lines])


def commit_message (prompt: str) -> str:
   from imp import validate

   msg = fast (prompt)
   msg = oneline (msg)

   if not validate.commit (msg):
      console.warn ("Retrying (invalid format)...")
      msg = fast (prompt)
      msg = oneline (msg)

      if not validate.commit (msg):
         console.err ("AI output not in Conventional Commits format")
         console.muted (msg)
         raise typer.Exit (1)

   return msg
