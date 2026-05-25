#!/usr/bin/env bash
# Repo with a couple of commits, then a staged change that should fix up one of them.
# Used by fixup.
set -e

REPO=/tmp/demo-repo
rm -rf "$REPO"
mkdir -p "$REPO"
cd "$REPO"

git init -q -b main
git config user.email "dev@example.com"
git config user.name "Dev"
git config commit.gpgsign false

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
    return user == "admin"
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: wire rate limit into login"

cat > README.md <<'EOF'
# Auth Service
EOF
git add README.md
git -c core.pager=cat commit -q -m "docs: add readme stub"

# Now stage a small change that obviously belongs to the rate limiter commit.
sed -i 's/MAX_ATTEMPTS = 5/MAX_ATTEMPTS = 10/' rate_limit.py
git add rate_limit.py

echo "$REPO"
