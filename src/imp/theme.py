from dataclasses import dataclass


@dataclass (frozen=True)
class Theme:
   accent: str = "#1eff00"
   success: str = "#00ff00"
   error: str = "#ff3131"
   warning: str = "#ff8000"
   muted: str = "#4e7a4e"
   highlight: str = "#a335ee"


theme = Theme ()
