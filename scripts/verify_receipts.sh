#!/usr/bin/env bash
# Slice 02 — Receipt Validation Gate.
# Validates every FailureHarvestReceipt under sandbox/receipts/ and verifies
# that none has been mutated since it was sealed (the receipt_hash field
# commits to the rest of the document).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
export PYTHONPATH="$HERE/src:${PYTHONPATH:-}"
python3 -m failureforge.cli verify-receipts
