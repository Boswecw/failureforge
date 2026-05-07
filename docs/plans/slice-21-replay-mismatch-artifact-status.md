# FailureForge Slice 21 - Replay Mismatch Artifact Status

Slice 21 makes replay run artifacts reflect deterministic replay mismatches.

## Purpose

`failureforge replay` already returns exit code `2` when a replayed attack no
longer matches the original receipt. After Slice 20, replay also writes a run
artifact, so that artifact must carry the same failure signal instead of
claiming a successful replay.

## Rules

- replay mismatches still return a `ReplayResult`
- replay mismatches do not raise `CanonicalSourceMutationError`
- replay mismatches write `SandboxRun.v1` with `status: failed`
- replay mismatches write `exit_code.txt` as `2`
- canonical mutation replay failures still take precedence with exit code `5`
- successful replay matches still write `status: completed` and exit code `0`
