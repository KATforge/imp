#!/bin/bash
#
# Shared helpers
#

IMP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source "$IMP_ROOT/lib/ai.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MUTED='\033[0;90m'
BOLD='\033[1m'
RESET='\033[0m'

# Output helpers
header() {
   echo
   echo -e "${BOLD}$1${RESET}"
   echo
}

label() {
   echo -e "${CYAN}$1${RESET}"
}

item() {
   echo -e "  ${MUTED}$1${RESET}"
}

divider() {
   echo -e "${MUTED}────────────────────────────────────────${RESET}"
}

err() {
   echo -e "${RED}error:${RESET} $1" >&2
}

warn() {
   echo -e "${YELLOW}$1${RESET}"
}

info() {
   echo -e "${BLUE}$1${RESET}"
}

muted() {
   echo -e "${MUTED}$1${RESET}"
}

success() {
   echo -e "${GREEN}✓${RESET} $1"
}

hint() {
   echo
   echo -e "${MUTED}→ $1${RESET}"
}

# Prompt for confirmation
confirm() {
   local msg="${1:-Continue?}"
   local default="${2:-y}"

   if [[ "$default" == "y" ]]; then
      read -rp "$msg [Y/n] "
   else
      read -rp "$msg [y/N] "
   fi

   case "$REPLY" in
      [Yy]*) return 0 ;;
      [Nn]*) return 1 ;;
      "")
         [[ "$default" == "y" ]] && return 0 || return 1
         ;;
      *) return 1 ;;
   esac
}

# Bump semver
bump_version() {
   local version="$1"
   local bump="$2"
   local major minor patch

   IFS='.' read -r major minor patch <<< "$version"

   case "$bump" in
      major) echo "$((major + 1)).0.0" ;;
      minor) echo "$major.$((minor + 1)).0" ;;
      patch) echo "$major.$minor.$((patch + 1))" ;;
      *) echo "$bump" ;;
   esac
}

# Get last git tag
last_tag() {
   git describe --tags --abbrev=0 2> /dev/null || echo ""
}

# Check if in git repo
require_git() {
   git rev-parse --git-dir > /dev/null 2>&1 || {
      err "Not a git repository"
      exit 1
   }
}
