# FailureForge Slice 20 - Replay Canonical Mutation Guard

Slice 20 makes deterministic replay fail closed if the canonical source changes
during replay execution.

## Purpose

Slices 16-17 protected sandbox runs with canonical source fingerprints. Replay
copies the same canonical source and executes attack logic against the copy, so
it needs the same before/after source guard instead of relying only on the
caller to catch a future exception.

## Rules

- `replay_receipt` hashes the canonical target source before copying
- replay writes a `SandboxRun.v1` record under the deterministic replay run id
- replay writes stdout/stderr and `exit_code.txt` in the replay run directory
- if the canonical source hash changes, replay writes a failed `SandboxRun.v1`
- failed replay mutation writes exit code `5`
- failed replay mutation raises `CanonicalSourceMutationError`
- replay never writes new `FailureHarvestReceipt` files
