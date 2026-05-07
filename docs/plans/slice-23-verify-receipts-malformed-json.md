# FailureForge Slice 23 - Verify Receipts Malformed JSON

Slice 23 makes receipt verification treat malformed receipt JSON as a normal
validation failure.

## Purpose

`failureforge verify-receipts` is the local evidence gate. It should report
every invalid receipt in its JSON summary, including files that cannot be
decoded as JSON, instead of surfacing a traceback before the summary is built.

## Rules

- malformed receipt JSON returns exit code `2`
- malformed receipt JSON is included in the `failures` summary
- other receipts continue to be checked
- no traceback is printed for malformed receipt files
- no-receipt behavior remains exit code `1`
