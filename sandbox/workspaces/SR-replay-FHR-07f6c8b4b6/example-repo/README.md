# example-repo (FailureForge demo target)

A toy registry with one deliberate invariant violation:

> Duplicate input must not create duplicate canonical records.

`registry.upsert(...)` ignores the `key` field and creates a new id per call.
The FailureForge Edge-Case Agent's `duplicate_replay` attack exposes this bug.

This directory is the **canonical** target. The sandbox copies it into
`sandbox/workspaces/<run-id>/example-repo/` before running attacks; never
modify the canonical copy from inside the sandbox.
