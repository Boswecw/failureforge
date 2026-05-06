#!/usr/bin/env bash
# Run one FailureForge sandbox session against the example target.
#
# Doctrine reminders:
# - destructive execution happens in sandbox/workspaces/<run>/, never the
#   canonical sandbox-targets/ copy.
# - every receipt has expected_result, actual_result, repro_command.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

TARGET="${1:-example-repo}"
SOURCE_REF="${2:-local}"
export PYTHONPATH="$HERE/src:${PYTHONPATH:-}"

python3 -m failureforge.cli run-sandbox --target "$TARGET" --source-ref "$SOURCE_REF"
