#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="$ROOT/doc/FFGSYSTEM.md"

{
  echo "# FFGSYSTEM"
  echo
  echo "Generated from doc/system on $(date -u +%Y-%m-%dT%H:%M:%SZ)."
  echo
  for file in \
    "$HERE/00-purpose.md" \
    "$HERE/10-current-architecture.md" \
    "$HERE/20-contracts.md" \
    "$HERE/30-integration-boundaries.md" \
    "$HERE/40-verification-gates.md"
  do
    cat "$file"
    echo
  done
} > "$OUT"

echo "$OUT"
