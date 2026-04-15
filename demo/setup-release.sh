#!/usr/bin/env bash
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
    return user == "admin" and password == "secret"
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: add login"

git remote add origin "$ORIGIN"
git push -q -u origin main

cat > rate_limit.py <<'EOF'
from time import time

_attempts = {}
WINDOW = 60
MAX_ATTEMPTS = 5

def allow(ip: str) -> bool:
    now = time()
    _attempts.setdefault(ip, [])
    _attempts[ip] = [t for t in _attempts[ip] if now - t < WINDOW]
    if len(_attempts[ip]) >= MAX_ATTEMPTS:
        return False
    _attempts[ip].append(now)
    return True
EOF

cat > auth.py <<'EOF'
from rate_limit import allow

def login(user, password, ip):
    if not allow(ip):
        return 429
    return user == "admin" and password == "secret"
EOF

echo "$REPO"
