#!/usr/bin/env bash
# Multi-file dirty working tree on a clean main. Used by split, ship, stash, fleet.
set -e

REPO=/tmp/demo-repo
rm -rf "$REPO"
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

mkdir -p tests
cat > tests/test_rate_limit.py <<'EOF'
from rate_limit import allow

def test_under_cap():
    for _ in range(5):
        assert allow("1.2.3.4")

def test_over_cap():
    for _ in range(5):
        allow("9.9.9.9")
    assert not allow("9.9.9.9")
EOF

cat > README.md <<'EOF'
# Auth Service

Rate-limited login. Configure WINDOW and MAX_ATTEMPTS in rate_limit.py.
EOF

echo "$REPO"
