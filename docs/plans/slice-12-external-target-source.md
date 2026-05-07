# FailureForge Slice 12 - External Target Source Gate

Slice 12 lets the CLI accept an explicit canonical target source path only when
a `TargetAdapter.v1` file is supplied.

## Purpose

The demo target remains available through:

```text
failureforge run-sandbox --target example-repo
```

Any non-default target source must use:

```text
failureforge run-sandbox --target <repo-name> --target-source <path> --adapter <adapter.json>
```

## Rules

- `--target-source` without `--adapter` fails before sandbox execution.
- relative target-source paths are resolved from the FailureForge repo root.
- the adapter guard still checks target name, sandbox boundary, canonical
  mutation guard, forbidden paths, and supported attack families.
- no new attack families are added.
- canonical sources are copied before execution; they are never attacked in
  place.
