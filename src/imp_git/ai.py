import json
import os
import re
import subprocess
import urllib.error
import urllib.request

from imp_git import config, console

MAX_DIFF_LINES = 2000
MAX_DIFF_CHARS = 100_000

_ATTRIBUTION_RULE = """\
Authorship rule:
- Never identify an AI agent, model, provider, or bot as an author, co-author, contributor, or generator.
- Never add Co-Authored-By, attribution trailers, signatures, generated-by notices, or actor IDs."""

def _guard (prompt: str) -> str:
   return f"{prompt.rstrip ()}\n\n{_ATTRIBUTION_RULE}\n"

def _claude (prompt: str, model: str) -> str:
   api_key = os.environ.get ("ANTHROPIC_API_KEY")
   if api_key:
      return _claude_sdk (prompt, model, api_key)
   return _claude_cli (prompt, model)

def _claude_sdk (prompt: str, model: str, api_key: str) -> str:
   import anthropic

   client = anthropic.Anthropic (api_key=api_key)

   try:
      response = client.messages.create (
         model=model,
         max_tokens=8192,
         temperature=0.3,
         messages=[
            {
               "role": "user",
               "content": [
                  {
                     "type": "text",
                     "text": prompt,
                     "cache_control": { "type": "ephemeral" },
                  },
               ],
            },
         ],
      )
   except anthropic.APIError as e:
      console.fatal (f"anthropic api failed: {e}")

   return "".join (block.text for block in response.content if getattr (block, "text", None))

def _claude_cli (prompt: str, model: str) -> str:
   result = subprocess.run (
      [
         "claude", "-p",
         "--model", model,
         "--tools", "",
      ],
      input=prompt,
      capture_output=True,
      text=True,
      cwd="/tmp",
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
      "think": False,
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

_PROVIDERS = {
   "claude": _claude,
   "ollama": _ollama,
}

def _call (prompt: str, model: str) -> str:
   provider = config.get ("provider")
   handler = _PROVIDERS.get (provider)

   if not handler:
      console.fatal (f"Unknown AI provider: {provider}")

   return handler (prompt, model)

def _invoke (tier: str, prompt: str, spin: bool = True) -> str:
   model = config.get (f"{tier}model")
   prompt = _guard (prompt)
   if spin:
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
      model = config.get ("fastmodel")
      result = _call ("Reply with OK", model)
      return bool (result and result.strip ())
   except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, SystemExit):
      return False

def strip_fences (text: str) -> str:
   text = re.sub (r"^```\w*\n?", "", text, flags=re.MULTILINE)
   return re.sub (r"\n?```$", "", text.strip ())

def oneline (text: str) -> str:
   return text.replace ("\n", "").strip ()

def truncate (
   text: str,
   max_lines: int = MAX_DIFF_LINES,
   max_chars: int = MAX_DIFF_CHARS,
) -> str:
   lines = text.splitlines ()
   value = text if len (lines) <= max_lines else "\n".join (lines [:max_lines])
   return value [:max_chars]

def commit_message (prompt: str) -> str:
   from imp_git import validate

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

def json_payload (prompt: str, spin: bool = True) -> dict:
   from imp_git import state

   for _attempt in range (2):
      raw = strip_fences (_invoke ("smart", prompt, spin))
      start = raw.find ("{")
      end = raw.rfind ("}")
      if start < 0 or end <= start:
         continue
      try:
         value = json.loads (raw [start:end + 1])
      except json.JSONDecodeError:
         continue
      if isinstance (value, dict):
         return value
   raise state.StateError ("AI did not return the requested JSON")

def review_diff (diff: str, spin: bool = True) -> dict:
   from imp_git import prompts

   return json_payload (prompts.review (truncate (diff)), spin)

def answer (diff: str, question: str) -> str:
   from imp_git import prompts

   return smart (prompts.answer (truncate (diff), question)).strip ()

def verdict (name: str, age: str, diff: str) -> dict:
   from imp_git import prompts

   return json_payload (prompts.verdict (name, age, truncate (diff)))
