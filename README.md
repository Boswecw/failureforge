# FailureForge

Sandbox-only failure-harvesting subsystem. Per the
`docs/plans/failureforge_repo_reconciled_plan_set` plan, this directory
implements Slices 01–03:

- **Slice 01** — `FailureCase.v1`, `FailureHarvestReceipt.v1`, `SandboxRun.v1`,
  `HardeningReport.v1` contracts + an Edge-Case Agent + `run_sandbox_once.sh`
  + `replay_failure.sh` + sample receipt + sample hardening report.
- **Slice 02** — Receipt validation gate (`verify_receipts.sh`,
  schema validation, required-field checks, immutable receipt hash).
- **Slice 03** — Hardening report ranking (`score_findings.py`,
  `HardeningReport.v1` JSON + `HardeningReport.md`).

## Doctrine

- All destructive testing happens against **copied workspaces**, never
  against canonical repos.
- Receipts are immutable after write. Modifying a receipt invalidates its
  hash and fails verification.
- No patch promotion without operator approval (Slice 06+ — out of scope here).
- Every reproducible failure has a replay command. Non-reproducible failures
  are explicitly marked.

## Layout

```
failureforge/
  schemas/                  # JSON schemas for the four Slice 01 contracts
  fixtures/{valid,invalid}/ # contract fixtures
  src/failureforge/
    agents/edge_case.py     # Edge-Case Agent
    runtime/sandbox.py      # SandboxRunner — copies workspace, runs lane, writes receipts
    runtime/replay.py       # Replay helper used by replay_failure.sh
    reporting/scorer.py     # Slice 03 ranking + HardeningReport generator
    validation/             # JSON Schema + receipt-hash validators
  tests/                    # pytest suite
  sandbox/
    workspaces/             # copied repo workspaces (gitignored in real use)
    runs/                   # per-run sandbox_run.json + stdout/stderr
    receipts/               # FailureHarvestReceipt JSON
    reports/                # HardeningReport JSON + Markdown
  sandbox-targets/
    example-repo/           # tiny target used by the demo run
  scripts/
    run_sandbox_once.sh
    replay_failure.sh
    verify_receipts.sh
```

## Demo

```bash
bash scripts/run_sandbox_once.sh
bash scripts/verify_receipts.sh
bash scripts/replay_failure.sh sandbox/receipts/<receipt-id>.json
```
