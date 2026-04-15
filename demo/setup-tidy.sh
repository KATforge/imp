#!/usr/bin/env bash
set -e

REPO=/tmp/demo-repo
rm -rf "$REPO"
mkdir -p "$REPO"
cd "$REPO"

git init -q -b main
git config user.email "dev@example.com"
git config user.name "Dev"
git config commit.gpgsign false
git config advice.detachedHead false

cat > README.md <<'EOF'
# Auth Service
EOF
git add README.md
git -c core.pager=cat commit -q -m "chore: initial commit"

cat > auth.py <<'EOF'
def login(user, passwrd):
    return user == "admin" and passwrd == "secret"
EOF
git add auth.py
git -c core.pager=cat commit -q -m "wip: login"

sed -i 's/passwrd/password/g' auth.py
git add auth.py
git -c core.pager=cat commit -q -m "fix typo"

cat >> README.md <<'EOF'

## Login

Use the `login(user, password)` function.
EOF
git add README.md
git -c core.pager=cat commit -q -m "docs: document login"

echo "$REPO"
