# FailureForge Slice 11 - Target Adapter Guard

Slice 11 adds the `TargetAdapter.v1` contract and runtime guard required before
FailureForge expands beyond demo targets.

## Purpose

FailureForge may only probe a target when the target's adapter declares:

- supported attack families
- copy-only workspace strategy
- read-only checks
- forbidden target paths
- sandbox-only artifact roots
- pre/post canonical mutation verification

## Non-Goals

- no new attack families
- no direct patching
- no canonical repo mutation
- no automatic target discovery
- no bypass of operator review

## Acceptance

- valid `TargetAdapter.v1` fixture validates
- invalid adapter fixtures fail validation
- mismatched adapter target is rejected
- canonical source inside `sandbox/` is rejected
- unsupported attack families fail before workspace copy
- existing sandbox run behavior remains compatible without an adapter
