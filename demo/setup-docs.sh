#!/usr/bin/env bash
# Repo wired to a sibling docs site via .imp, with a release tag and a feature
# commit after it. imp docs finds the page the change makes stale. Used by the
# docs demo.
set -e

REPO=/tmp/demo-repo
DOCS=/tmp/docs-site

rm -rf "$REPO" "$DOCS"

mkdir -p "$DOCS/reference"
cat > "$DOCS/reference/commands.md" <<'EOF'
# Commands

## login
Authenticate a user.
EOF

mkdir -p "$REPO"
cd "$REPO"

git init -q -b main
git config user.email "dev@example.com"
git config user.name "Dev"
git config commit.gpgsign false

cat > .imp <<'EOF'
{
   "docs:mode": "reconcile",
   "docs:path": "../docs-site"
}
EOF

cat > auth.py <<'EOF'
def login(user, password):
    return user == "admin" and password == "secret"
EOF
git add .imp auth.py
git -c core.pager=cat commit -q -m "feat: add login"
git tag v0.1.0

cat >> auth.py <<'EOF'

def logout(session):
    session.clear()
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: add logout endpoint"

echo "$REPO"
