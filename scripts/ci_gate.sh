#!/usr/bin/env bash
# FailureForge local proof gate. Fails closed and writes evidence under reports/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
export PYTHONPATH="$HERE/src:${PYTHONPATH:-}"

OUT="$HERE/reports/failureforge-verification/latest"
rm -rf "$OUT"
mkdir -p "$OUT"

write_exit() {
  local name="$1"
  local code="$2"
  printf "%s\n" "$code" > "$OUT/${name}_exit.txt"
}

run_step() {
  local name="$1"
  local fail_code="$2"
  shift 2
  set +e
  "$@" >"$OUT/${name}_stdout.txt" 2>"$OUT/${name}_stderr.txt"
  local code=$?
  set -e
  write_exit "$name" "$code"
  if [[ "$code" -ne 0 ]]; then
    {
      echo "# FailureForge CI Gate Summary"
      echo
      echo "- status: failed"
      echo "- failed_step: $name"
      echo "- command_exit: $code"
      echo "- gate_exit: $fail_code"
    } > "$OUT/summary.md"
    exit "$fail_code"
  fi
}

run_step dependency_check 2 python3 -c "import jsonschema, httpx, pytest; import failureforge"
run_step ruff_check 6 ruff check src tests
run_step ruff_format 7 ruff format --check src tests
run_step doc_build 1 bash doc/system/BUILD.sh
run_step pytest 1 python3 -m pytest
run_step sandbox_run 1 bash scripts/run_sandbox_once.sh example-repo ci-gate
run_step receipt_verify 3 bash scripts/verify_receipts.sh

receipt_path="$(python3 - <<'PY'
from pathlib import Path
paths = sorted(Path("sandbox/receipts").glob("FHR-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not paths:
    raise SystemExit(1)
print(paths[0])
PY
)"
printf "%s\n" "$receipt_path" > "$OUT/replay_receipt_path.txt"
cp "$receipt_path" "$OUT/replay_receipt.json"
run_step replay 4 bash scripts/replay_failure.sh "$receipt_path"
run_step no_canonical_mutation 5 bash scripts/verify_no_canonical_mutation.sh

{
  echo "# FailureForge CI Gate Summary"
  echo
  echo "- status: passed"
  echo "- dependency_check: $(cat "$OUT/dependency_check_exit.txt")"
  echo "- ruff_check: $(cat "$OUT/ruff_check_exit.txt")"
  echo "- ruff_format: $(cat "$OUT/ruff_format_exit.txt")"
  echo "- pytest: $(cat "$OUT/pytest_exit.txt")"
  echo "- sandbox_run: $(cat "$OUT/sandbox_run_exit.txt")"
  echo "- receipt_verify: $(cat "$OUT/receipt_verify_exit.txt")"
  echo "- replay: $(cat "$OUT/replay_exit.txt")"
  echo "- replay_receipt: $receipt_path"
  echo "- replay_receipt_copy: reports/failureforge-verification/latest/replay_receipt.json"
  echo "- no_canonical_mutation: $(cat "$OUT/no_canonical_mutation_exit.txt")"
  echo "- doc_build: $(cat "$OUT/doc_build_exit.txt")"
} > "$OUT/summary.md"
