#!/bin/bash
#
# Pluggable AI interface
# string in → string out
#

AI_PROVIDER="${IMP_AI_PROVIDER:-claude}"
AI_MODEL_FAST="${IMP_AI_MODEL_FAST:-haiku}"
AI_MODEL_SMART="${IMP_AI_MODEL_SMART:-sonnet}"

ai() {
   local prompt="$1"
   local model="${2:-$AI_MODEL_FAST}"

   if [[ -z "$prompt" ]]; then
      echo "error: empty prompt" >&2
      return 1
   fi

   local result=""

   case "$AI_PROVIDER" in
      claude)
         if ! command -v claude &> /dev/null; then
            echo "error: claude CLI not installed" >&2
            return 1
         fi
         result=$(claude -p "$prompt" --model "$model" --max-turns 1 2> /dev/null)
         ;;
      ollama)
         if ! command -v curl &> /dev/null || ! command -v jq &> /dev/null; then
            echo "error: curl and jq required for ollama" >&2
            return 1
         fi
         result=$(curl -sf localhost:11434/api/generate \
            -d "$(jq -n --arg p "$prompt" --arg m "$model" \
               '{model:$m, prompt:$p, stream:false}')" \
            | jq -r '.response') || {
            echo "error: ollama request failed" >&2
            return 1
         }
         ;;
      *)
         echo "error: unknown AI provider: $AI_PROVIDER" >&2
         return 1
         ;;
   esac

   if [[ -z "$result" ]]; then
      echo "error: empty response from AI" >&2
      return 1
   fi

   echo "$result"
}

ai_fast() {
   ai "$1" "$AI_MODEL_FAST"
}

ai_smart() {
   ai "$1" "$AI_MODEL_SMART"
}
