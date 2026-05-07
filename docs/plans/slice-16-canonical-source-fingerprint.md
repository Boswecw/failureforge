# FailureForge Slice 16 - Canonical Source Fingerprint

Slice 16 records per-run canonical source hashes in `SandboxRun.v1`.

## Purpose

The no-canonical-mutation verifier proves the demo target is unchanged. Every
runner-produced `SandboxRun.v1` should also carry its own source fingerprint so
adapter-backed external runs have local proof that the canonical source was not
modified during sandbox execution.

## Rules

- hash the canonical source tree before workspace copy
- hash the canonical source tree again after agents finish
- record both hashes in `SandboxRun.v1`
- record `canonical_source_mutated`
- do not mutate receipts after sealing
- keep existing minimal `SandboxRun.v1` fixtures valid
