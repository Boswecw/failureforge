# FailureForge Slice 17 - Fail-Closed Canonical Mutation

Slice 17 turns canonical source hash drift into a hard sandbox failure.

## Purpose

Slice 16 records before/after canonical source hashes. Slice 17 makes any hash
change fail closed so mutated canonical sources cannot be returned as completed
evidence.

## Rules

- build receipts in memory while agents run
- hash canonical source again before receipt files are written
- if the source hash changed, write a failed `SandboxRun.v1`
- write run exit code `5`
- raise `CanonicalSourceMutationError`
- do not write receipt files for the failed run
