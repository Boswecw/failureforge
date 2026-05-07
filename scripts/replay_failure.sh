#!/usr/bin/env bash
# Replay a FailureHarvestReceipt deterministically.
# Usage: ./scripts/replay_failure.sh sandbox/receipts/FHR-XXX.json [--target-source path --adapter adapter.json]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

if [[ "$#" -lt 1 ]]; then
  echo "usage: $0 <receipt-path>" >&2
  exit 64
fi

export PYTHONPATH="$HERE/src:${PYTHONPATH:-}"
python3 -m failureforge.cli replay "$@"
