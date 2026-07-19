#!/usr/bin/env bash
# Repo whose package.json version has drifted below the git tag. imp version
# reports the drift; --sync rewrites it. Used by the version demo.
set -e

REPO=/tmp/demo-repo
rm -rf "$REPO"
mkdir -p "$REPO"
cd "$REPO"

git init -q -b main
git config user.email "dev@example.com"
git config user.name "Dev"
git config commit.gpgsign false

cat > package.json <<'EOF'
{
  "name": "auth-service",
  "version": "0.0.5"
}
EOF
git add package.json
git -c core.pager=cat commit -q -m "feat: cut auth service"
git tag v0.0.6

echo "$REPO"
