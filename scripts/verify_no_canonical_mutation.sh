#!/usr/bin/env bash
# Verify that a sandbox run cannot mutate the canonical example target.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
export PYTHONPATH="$HERE/src:${PYTHONPATH:-}"

hash_target() {
  python3 - "$HERE/sandbox-targets/example-repo" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
digest = hashlib.sha256()
for path in sorted(p for p in root.rglob("*") if p.is_file()):
    digest.update(str(path.relative_to(root)).encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
}

before="$(hash_target)"
python3 -m failureforge.cli run-sandbox \
  --target example-repo \
  --source-ref no-canonical-mutation \
  --run-id SR-no-canonical-mutation >/dev/null
after="$(hash_target)"

if [[ "$before" != "$after" ]]; then
  echo "canonical target hash changed: before=$before after=$after" >&2
  exit 5
fi

printf '{"canonical_target":"sandbox-targets/example-repo","hash":"%s","mutated":false}\n' "$after"
