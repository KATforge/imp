#!/usr/bin/env bash
# Directory containing three small dirty repos. Used by fleet.
set -e

ROOT=/tmp/demo-fleet
rm -rf "$ROOT"
mkdir -p "$ROOT"

mk () {
   local name=$1 ; local subject=$2
   mkdir -p "$ROOT/$name"
   cd "$ROOT/$name"
   git init -q -b main
   git config user.email "dev@example.com"
   git config user.name "Dev"
   git config commit.gpgsign false
   cat > pyproject.toml <<EOF
[project]
name = "$name"
version = "0.0.1"
EOF
   git add pyproject.toml
   git -c core.pager=cat commit -q -m "chore: initial commit"

   echo "$subject" > FEATURE.md
}

mk auth-service "Add per-IP rate limiting to login"
mk billing-api  "Surface refund history in admin console"
mk web-client   "Bump rate limit headers on 429"

echo "$ROOT"
