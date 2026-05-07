# FailureForge Slice 19 - CLI Replay Canonical Mutation Exit

Slice 19 applies the canonical mutation exit contract to deterministic replay.

## Purpose

Slice 18 gave `run-sandbox` a controlled CLI result for
`CanonicalSourceMutationError`. Replay uses the same target-source and adapter
guard surface, so it must report the same fail-closed condition without a
traceback.

## Rules

- `failureforge replay` catches `CanonicalSourceMutationError`
- the command prints a concise error to stderr
- the command returns exit code `5`
- replay JSON is not emitted after a canonical mutation failure
- receipt validation and target-source adapter requirements remain unchanged
