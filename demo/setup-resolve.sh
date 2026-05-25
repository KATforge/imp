#!/usr/bin/env bash
# Repo left mid-merge with one conflict in auth.py. Used by resolve.
set -e

# Build the same starting state as setup-conflict, then start the merge.
bash /usr/local/bin/setup-conflict >/dev/null

cd /tmp/demo-repo
git -c core.pager=cat merge --no-edit feat/per-user-limits 2>/dev/null || true

echo /tmp/demo-repo
