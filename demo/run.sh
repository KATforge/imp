#!/usr/bin/env bash
# Render all demo GIFs via VHS in Docker. Run from the repo root or demo/.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

docker build -f demo/Dockerfile -t imp-demo .

for tape in tidy commit pr release; do
   echo "▸ rendering $tape.gif"
   docker run --rm -v "$ROOT/demo:/vhs" imp-demo "$tape.tape"
done

echo "✓ demo/tidy.gif demo/commit.gif demo/pr.gif demo/release.gif"
