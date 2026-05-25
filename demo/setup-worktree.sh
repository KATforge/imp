#!/usr/bin/env bash
# Repo with two existing worktrees. Used by worktree list/path/remove/prune/add.
set -e

REPO=/tmp/demo-repo
rm -rf "$REPO" /tmp/.worktrees
mkdir -p "$REPO"
cd "$REPO"

git init -q -b main
git config user.email "dev@example.com"
git config user.name "Dev"
git config commit.gpgsign false
git config advice.detachedHead false

cat > auth.py <<'EOF'
def login(user, password):
    return True
EOF
git add auth.py
git -c core.pager=cat commit -q -m "feat: add login"

mkdir -p /tmp/.worktrees/demo-repo
git worktree add -q -b feat/rate-limit /tmp/.worktrees/demo-repo/feat-rate-limit >/dev/null
git worktree add -q -b fix/login-error /tmp/.worktrees/demo-repo/fix-login-error >/dev/null

# Make HOME point at a writable path that holds the .worktrees dir so
# `imp worktree add` defaults land somewhere predictable.
export HOME=/tmp

echo "$REPO"
