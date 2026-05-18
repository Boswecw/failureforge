# 40 Verification Gates

The local proof gate is `bash scripts/ci_gate.sh`.

It writes evidence under `reports/failureforge-verification/latest/` and runs:

- dependency import check
- `python3 -m pytest`
- sandbox demo run
- receipt schema/hash verification
- deterministic replay
- no-canonical-mutation verification
- target adapter schema and preflight tests
- external target-source adapter requirement tests
- adapter required-command and forbidden-source-path tests
- adapter-aware external-source replay tests
- replay command context tests for adapter-backed receipts
- canonical source fingerprint tests
- fail-closed canonical mutation tests
- CLI canonical mutation exit tests
- CLI replay canonical mutation exit tests
- replay canonical mutation guard tests
- replay mismatch artifact status tests
- CLI replay receipt validation tests
- verify-receipts malformed JSON tests
- CLI adapter load validation tests
- documentation assembly

Supporting commands:

- `bash scripts/verify_receipts.sh`
- `bash scripts/replay_failure.sh sandbox/receipts/<receipt>.json`
- `bash scripts/verify_no_canonical_mutation.sh`
- `bash doc/system/BUILD.sh`
