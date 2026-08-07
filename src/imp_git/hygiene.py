from pathlib import PurePosixPath


def inspect (paths: list [str]) -> tuple [list [str], list [str]]:
   """Return deterministic ignore-policy warnings and secret blockers."""

   warnings = []
   blockers = []
   generated_parts = {
      ".pytest_cache",
      ".ruff_cache",
      ".venv",
      "__pycache__",
      "build",
      "dist",
      "node_modules",
   }
   secret_names = { ".env", "id_dsa", "id_ed25519", "id_rsa" }
   secret_suffixes = { ".key", ".p12", ".pfx", ".pem" }

   for value in paths:
      path = PurePosixPath (value)
      lower = path.name.lower ()
      if any (part in generated_parts for part in path.parts) or path.suffix.lower () in { ".log", ".pyc", ".tmp" }:
         warnings.append (f"Possible ignore candidate: {value}")
      is_secret = lower in secret_names or (
         lower.startswith (".env.") and not lower.endswith ((".example", ".sample"))
      )
      if is_secret or path.suffix.lower () in secret_suffixes:
         blockers.append (f"Possible secret file requires explicit review: {value}")

   return warnings, blockers
