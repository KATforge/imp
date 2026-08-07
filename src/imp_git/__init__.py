from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _v

try:
   __version__ = _v ("imp-git")
except PackageNotFoundError:
   __version__ = "dev"
