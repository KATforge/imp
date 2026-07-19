#!/usr/bin/env bash
# Repo with a sibling docs site and no .imp yet. imp setup detects the docs
# path and writes the .imp. Used by the setup demo.
set -e

REPO=/tmp/demo-repo
DOCS=/tmp/docs-site

rm -rf "$REPO" "$DOCS"

mkdir -p "$DOCS/content/reference" "$DOCS/content/guides"
echo "# Commands" > "$DOCS/content/reference/commands.md"
echo "# Getting started" > "$DOCS/content/guides/intro.md"

mkdir -p "$REPO"
cd "$REPO"

git init -q -b main
git config user.email "dev@example.com"
git config user.name "Dev"
git config commit.gpgsign false

cat > auth.py <<'EOF'
def login(user, password):
    return user == "admin" and password == "secret"
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: add login"

echo "$REPO"
