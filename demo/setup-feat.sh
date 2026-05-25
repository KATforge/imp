#!/usr/bin/env bash
# Repo on a feature branch with commits ready to PR. Used by pr, push, sync,
# done, clean.
set -e

REPO=/tmp/demo-repo
ORIGIN=/tmp/demo-origin.git

rm -rf "$REPO" "$ORIGIN"
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
git -c core.pager=cat commit -q -m "feat: add login stub"

git remote add origin "$ORIGIN"
git push -q -u origin main

git checkout -q -b feat/rate-limit

cat > rate_limit.py <<'EOF'
from time import time

_attempts = {}
WINDOW = 60
MAX_ATTEMPTS = 5

def allow(ip):
    now = time()
    _attempts.setdefault(ip, [])
    _attempts[ip] = [t for t in _attempts[ip] if now - t < WINDOW]
    if len(_attempts[ip]) >= MAX_ATTEMPTS:
        return False
    _attempts[ip].append(now)
    return True
EOF
git add rate_limit.py
git -c core.pager=cat commit -q -m "feat: add rate limiter primitive"

cat > auth.py <<'EOF'
from rate_limit import allow

def login(user, password, ip):
    if not allow(ip):
        return 429
    return True
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: wire rate limit into login"

git push -q -u origin feat/rate-limit

echo "$REPO"
