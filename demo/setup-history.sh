#!/usr/bin/env bash
# Clean repo with a few commits. Used by log, undo, revert, changelog, tag,
# standup, fixup, rescue, done.
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
git config advice.detachedHead false

cat > README.md <<'EOF'
# Auth Service
EOF
git add README.md
GIT_AUTHOR_DATE='2024-01-02T10:00:00' GIT_COMMITTER_DATE='2024-01-02T10:00:00' \
   git -c core.pager=cat commit -q -m "chore: initial commit"

cat > auth.py <<'EOF'
def login(user, password):
    return user == "admin" and password == "secret"
EOF
git add auth.py
GIT_AUTHOR_DATE='2024-01-03T11:00:00' GIT_COMMITTER_DATE='2024-01-03T11:00:00' \
   git -c core.pager=cat commit -q -m "feat: add login endpoint"

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
git add rate_limit.py
GIT_AUTHOR_DATE='2024-01-04T09:30:00' GIT_COMMITTER_DATE='2024-01-04T09:30:00' \
   git -c core.pager=cat commit -q -m "feat: add rate limiter primitive"

cat > auth.py <<'EOF'
from rate_limit import allow

def login(user, password, ip):
    if not allow(ip):
        return 429
    return user == "admin" and password == "secret"
EOF
git add auth.py
GIT_AUTHOR_DATE='2024-01-04T15:00:00' GIT_COMMITTER_DATE='2024-01-04T15:00:00' \
   git -c core.pager=cat commit -q -m "feat: wire rate limit into login"

cat >> README.md <<'EOF'

## Rate limiting

Configure WINDOW and MAX_ATTEMPTS in `rate_limit.py`.
EOF
git add README.md
GIT_AUTHOR_DATE='2024-01-05T08:15:00' GIT_COMMITTER_DATE='2024-01-05T08:15:00' \
   git -c core.pager=cat commit -q -m "docs: document rate limit knobs"

git remote add origin "$ORIGIN"
git push -q -u origin main

echo "$REPO"
