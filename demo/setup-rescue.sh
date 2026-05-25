#!/usr/bin/env bash
# Repo with an "orphaned" commit reachable only via the reflog. Used by rescue.
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
    return True
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: add login"

# Build a tempting "lost" commit on a throwaway branch, then nuke the branch.
git checkout -q -b experimental
cat > middleware.py <<'EOF'
def rate_limit(handler):
    seen = {}
    def wrapper(req):
        ip = req.headers.get("x-real-ip", "unknown")
        seen[ip] = seen.get(ip, 0) + 1
        if seen[ip] > 5:
            return 429
        return handler(req)
    return wrapper
EOF
git add middleware.py
git -c core.pager=cat commit -q -m "feat: add rate limit middleware"

git checkout -q main
git branch -q -D experimental

echo "$REPO"
