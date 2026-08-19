from imp_git import git

_DEFAULTS = {
   "provider": "claude",
   "fastmodel": "haiku",
   "smartmodel": "sonnet",
}


def get (key: str) -> str:
   """Read one machine or repository knob from Git configuration."""

   return git.config_get (f"imp.{key}") or _DEFAULTS.get (key, "")


def get_all (key: str) -> list [str]:
   return git.config_get_all (f"imp.{key}")


def snapshot () -> dict [str, str]:
   """Return the effective configuration: defaults overlaid with explicit imp.* entries."""

   values = dict (_DEFAULTS)
   for key, value in git.config_entries (r"^imp\.").items ():
      values [key.removeprefix ("imp.")] = value
   return values
