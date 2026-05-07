# FailureForge Slice 13 - Adapter Preflight Enforcement

Slice 13 makes declared `TargetAdapter.v1` preflight fields active runtime
checks.

## Purpose

Adapters already declare required commands and forbidden canonical-source
paths. This slice makes those declarations enforceable before sandbox workspace
copy.

## Rules

- every `required_commands` entry must resolve on `PATH`
- every `forbidden_paths` entry must be relative and contained
- a canonical source containing a forbidden path is rejected
- failures occur before workspace copy or artifact creation
- no new attack families are added
- canonical repos are still copied, never attacked in place
