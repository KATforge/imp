from imp import config, console


def _provider_choices () -> list [str]:
   return [ "claude", "ollama" ]


def _claude_models () -> list [str]:
   return [ "haiku", "sonnet", "opus" ]


def _ollama_models () -> list [str]:
   return [
      "llama3.2",
      "llama3.1",
      "mistral",
      "codellama",
      "custom",
   ]


def configure ():
   """Interactively configure AI provider and models.

   Sets the AI provider (Claude or Ollama) and which models to use for
   fast and smart operations. Configuration is stored in
   ~/.config/imp/config.json.
   """

   console.header ("Config")

   cfg = config.load ()

   console.muted (f"Config: {config.path ()}")
   console.out.print ()

   provider = console.choose ("AI provider", _provider_choices ())
   cfg ["provider"] = provider

   if provider == "claude":
      models = _claude_models ()
   else:
      models = _ollama_models ()

   fast = console.choose ("Fast model (commits, branches)", models)
   if fast == "custom":
      fast = console.prompt ("Model name:")
   cfg ["model:fast"] = fast

   smart = console.choose ("Smart model (review, PR, split)", models)
   if smart == "custom":
      smart = console.prompt ("Model name:")
   cfg ["model:smart"] = smart

   config.save (cfg)

   console.out.print ()
   console.success ("Saved")
   console.muted (f"  provider:    {cfg ['provider']}")
   console.muted (f"  model:fast:  {cfg ['model:fast']}")
   console.muted (f"  model:smart: {cfg ['model:smart']}")
   console.hint ("imp doctor to verify")
