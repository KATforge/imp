#!/usr/bin/env bash
# Local branch and its upstream have diverged on different files (no conflict).
# imp pull rebases the local commit onto the upstream one. Used by the pull demo.
set -e

REPO=/tmp/demo-repo
ORIGIN=/tmp/demo-origin.git
CLONE=/tmp/demo-clone

rm -rf "$REPO" "$ORIGIN" "$CLONE"
git init -q --bare -b main "$ORIGIN"

mkdir -p "$REPO"
cd "$REPO"

git init -q -b main
git config user.email "dev@example.com"
git config user.name "Dev"
git config commit.gpgsign false

cat > auth.py <<'EOF'
def login(user, password):
    return True
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: add login"
git remote add origin "$ORIGIN"
git push -q -u origin main

# A teammate pushes an upstream change to a different file.
git clone -q "$ORIGIN" "$CLONE"
cd "$CLONE"
git config user.email "teammate@example.com"
git config user.name "Teammate"
git config commit.gpgsign false
cat > config.py <<'EOF'
WINDOW = 60
MAX_ATTEMPTS = 5
EOF
git add config.py
git -c core.pager=cat commit -q -m "fix: tune rate limit window"
git push -q origin main

# Our local, unpushed work on yet another file — now diverged.
cd "$REPO"
cat > rate_limit.py <<'EOF'
def allow(ip):
    return True
EOF
git add rate_limit.py
git -c core.pager=cat commit -q -m "feat: add rate limiter primitive"

echo "$REPO"
