# FailureForge Slice 22 - CLI Replay Receipt Validation

Slice 22 makes replay receipt validation fail closed at the CLI boundary.

## Purpose

`failureforge replay` needs the receipt's `target_repo` to resolve the replay
target source. The command must validate receipt schema and hash before reading
that field so malformed or tampered receipts cannot surface tracebacks.

## Rules

- replay CLI reads the receipt under a controlled error boundary
- malformed JSON returns exit code `2`
- schema-invalid receipts return exit code `2`
- hash-invalid receipts return exit code `2`
- invalid receipts print a concise stderr message
- invalid receipts do not emit replay JSON
- invalid receipts do not copy a replay workspace
