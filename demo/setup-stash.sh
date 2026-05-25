#!/usr/bin/env bash
# Repo with two existing stashes plus a fresh dirty change. Used by stash *.
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

# Stash 1
echo "# experimental token bucket" > token_bucket.py
git -c core.pager=cat stash push -u -q -m "experiment with token bucket rate limiter"

# Stash 2
sed -i 's/admin/root/' auth.py
git -c core.pager=cat stash push -q -m "rename admin user to root"

# Fresh dirty change for new stash demos
cat > rate_limit.py <<'EOF'
from time import time

WINDOW = 60
MAX_ATTEMPTS = 5

_attempts = {}

def allow(ip):
    now = time()
    _attempts.setdefault(ip, [])
    _attempts[ip] = [t for t in _attempts[ip] if now - t < WINDOW]
    if len(_attempts[ip]) >= MAX_ATTEMPTS:
        return False
    _attempts[ip].append(now)
    return True
EOF

echo "$REPO"
