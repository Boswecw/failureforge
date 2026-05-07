# FailureForge Slice 18 - CLI Canonical Mutation Exit

Slice 18 maps fail-closed canonical mutation errors to the documented CLI exit
code.

## Purpose

Slice 17 made canonical source hash drift raise `CanonicalSourceMutationError`.
The command-line surface should report that failure without a traceback and
return the canonical mutation exit code.

## Rules

- `failureforge run-sandbox` catches `CanonicalSourceMutationError`
- the command prints a concise error to stderr
- the command returns exit code `5`
- no hardening report is built after the failed run
- the runner remains responsible for writing the failed `SandboxRun.v1`
