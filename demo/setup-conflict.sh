#!/usr/bin/env bash
# Repo with two branches that touch the same file. Merging produces a real
# conflict. Used by merge, resolve.
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
def login(user, password, ip):
    return user == "admin" and password == "secret"
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: add login"

# Side branch: per-user rate limiting
git checkout -q -b feat/per-user-limits
cat > auth.py <<'EOF'
from rate_limit import allow_user

def login(user, password, ip):
    if not allow_user(user):
        return 429
    return user == "admin" and password == "secret"
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: switch to per-user rate limit"

# Main: per-IP rate limiting on the same file
git checkout -q main
cat > auth.py <<'EOF'
from rate_limit import allow_ip

def login(user, password, ip):
    if not allow_ip(ip):
        return 429
    return user == "admin" and password == "secret"
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: add per-IP rate limit"

echo "$REPO"
