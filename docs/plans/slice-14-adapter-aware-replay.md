# FailureForge Slice 14 - Adapter-Aware Replay

Slice 14 makes replay compatible with adapter-backed external target sources.

## Purpose

Slice 12 allowed `run-sandbox` to use an explicit target source only when a
validated `TargetAdapter.v1` is supplied. Replay needs the same guard so
external-source receipts remain reproducible without falling back to the demo
target tree.

## Rules

- default replay still uses `sandbox-targets/<target_repo>`
- replay accepts `--target-source <path> --adapter <adapter.json>`
- `--target-source` without `--adapter` fails before replay execution
- adapter preflight runs before replay workspace copy
- forbidden source paths block replay
- no receipt mutation is performed
