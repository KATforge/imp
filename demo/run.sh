#!/usr/bin/env bash
# Render every demo GIF via VHS in Docker. Run from the repo root or demo/.
# Pass tape names (without .tape) as args to render a subset:
#   ./run.sh commit pr           # just those two
#   ./run.sh                     # all of them
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

if [ "${SKIP_BUILD:-0}" != "1" ] && ! docker image inspect imp-demo >/dev/null 2>&1; then
   docker build -f demo/Dockerfile -t imp-demo .
elif [ "${SKIP_BUILD:-0}" = "1" ]; then
   echo "▸ SKIP_BUILD=1; using existing imp-demo image"
else
   echo "▸ imp-demo image present; pass --rebuild to force rebuild"
fi

if [ "${1:-}" = "--rebuild" ]; then
   docker build -f demo/Dockerfile -t imp-demo .
   shift
fi

if [ "$#" -gt 0 ]; then
   tapes=("$@")
else
   mapfile -t tapes < <(cd demo && ls *.tape | sed 's/\.tape$//' | sort)
fi

failed=()
for tape in "${tapes[@]}"; do
   echo "▸ rendering ${tape}.gif"
   if docker run --rm -v "$ROOT/demo:/vhs" imp-demo "${tape}.tape"; then
      :
   else
      failed+=("$tape")
   fi
done

if [ "${#failed[@]}" -gt 0 ]; then
   echo "✗ failed: ${failed[*]}" >&2
   exit 1
fi

echo "✓ rendered ${#tapes[@]} GIFs"
