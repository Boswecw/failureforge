# FailureForge Slice 15 - Replay Command Context

Slice 15 makes receipt replay commands preserve adapter-backed target context.

## Purpose

External-source sandbox runs can now replay with `--target-source` and
`--adapter`, but receipts still need to carry that context in `repro_command`.
Without it, an otherwise valid receipt could replay against the demo target by
default.

## Rules

- default demo runs keep the existing replay command shape
- adapter-backed external runs include `--target-source`
- adapter-backed runs include `--adapter`
- replay command arguments are shell-quoted
- receipts remain immutable after sealing
