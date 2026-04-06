import json
import re
import subprocess
import urllib.error
import urllib.request

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
      timeout=300,
   )

   if result.returncode != 0:
      detail = result.stderr.strip () or result.stdout.strip ()
      console.fatal (f"claude CLI failed: {detail}" if detail else "claude CLI failed")

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
      with urllib.request.urlopen (req, timeout=60) as resp:
         body = json.loads (resp.read ())
         return body.get ("response", "")
   except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
      console.fatal (f"ollama request failed: {e}")


def _call (prompt: str, model: str) -> str:
   provider = config.get ("provider")
   if provider == "claude":
      return _claude (prompt, model)
   elif provider == "ollama":
      return _ollama (prompt, model)
   else:
      console.fatal (f"Unknown AI provider: {provider}")


def _invoke (tier: str, prompt: str, spin: bool = True) -> str:
   model = config.get (f"model:{tier}")
   if spin:
      console.out.print ()
      result = console.spin ("Thinking...", _call, prompt, model)
   else:
      result = _call (prompt, model)

   if not result or not result.strip ():
      console.fatal ("Empty response from AI")

   return result


def fast (prompt: str, spin: bool = True) -> str:
   return _invoke ("fast", prompt, spin)


def smart (prompt: str, spin: bool = True) -> str:
   return _invoke ("smart", prompt, spin)


def ping () -> bool:
   try:
      model = config.get ("model:fast")
      result = _call ("Reply with OK", model)
      return bool (result and result.strip ())
   except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, SystemExit):
      return False


def strip_fences (text: str) -> str:
   text = re.sub (r"^```\w*\n?", "", text, flags=re.MULTILINE)
   return re.sub (r"\n?```$", "", text.strip ())


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
         console.muted (msg)
         console.fatal ("AI output not in Conventional Commits format")

   return msg
