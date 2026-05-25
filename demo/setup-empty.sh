#!/usr/bin/env bash
# Empty directory, no git. Used by setup, config, doctor, help.
set -e

REPO=/tmp/demo-repo
rm -rf "$REPO"
mkdir -p "$REPO"
cd "$REPO"

cat > package.json <<'EOF'
{
  "name": "auth-service",
  "version": "0.0.0",
  "dependencies": {}
}
EOF

cat > index.js <<'EOF'
console.log("hello");
EOF

echo "$REPO"
