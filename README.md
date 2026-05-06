# FailureForge

Sandbox-only failure-harvesting subsystem. Per the
`docs/plans/failureforge_repo_reconciled_plan_set` plan, this directory
implements Slices 01-09:

- **Slice 01** - `FailureCase.v1`, `FailureHarvestReceipt.v1`, `SandboxRun.v1`,
  `HardeningReport.v1` contracts, Edge-Case Agent, sandbox run script, replay
  script, sample receipt, and sample hardening report.
- **Slice 02** - Receipt validation gate with schema validation,
  required-field checks, and immutable receipt hashes.
- **Slice 03** - Hardening report ranking with recommended fixes, receipt IDs,
  and replay commands.
- **Slice 04** - DataForge Local persistence shape, service boundary, and push
  client integration.
- **Slice 05** - Read-only operator report surface and morning-report CLI.
- **Slice 06** - Operator approval and SMITH handshake through typed receipts
  and an identity-gated FSM.
- **Slice 07** - Multi-agent expansion across chaos, mutation, reproduction,
  and classification lanes.
- **Slice 08** - Centipede root-cause clustering and ranked fix-cluster reports.
- **Slice 09** - NeuroForge comparative adjudication with model receipts and a
  deterministic final classification rule.

## Doctrine

- All destructive testing happens against **copied workspaces**, never against
  canonical repos.
- Receipts are immutable after write. Modifying a receipt invalidates its hash
  and fails verification.
- No direct patch promotion: operator approval and SMITH handoff are mediated
  by explicit promotion/approval receipts and FSM checks.
- Every reproducible failure has a replay command. Non-reproducible failures
  are explicitly marked.
- Cluster generation preserves source disagreement instead of flattening lane
  evidence into a single opaque result.
- NeuroForge provider votes can confirm or dispute a cluster, but final
  classification stays derived from deterministic cluster evidence.

## Layout

```
failureforge/
  schemas/                  # receipt, report, promotion, approval, cluster, adjudication contracts
  fixtures/{valid,invalid}/ # contract fixtures
  src/failureforge/
    agents/                 # edge_case, chaos, mutation, reproduction, classification
    adjudication/           # Slice 09 NeuroForge provider comparison
    clustering/centipede.py # Slice 08 root-cause clustering
    runtime/sandbox.py      # SandboxRunner: copies workspace, runs lanes, writes receipts
    runtime/replay.py       # Replay helper used by replay_failure.sh
    reporting/scorer.py     # Slice 03 ranking + HardeningReport generator
    validation/             # JSON Schema + receipt-hash validators
    cli.py                  # run-sandbox, replay, verify-receipts, morning-report
  tests/                    # pytest suite for Slices 01-09
  sandbox/
    workspaces/             # copied repo workspaces
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

DataForge Local owns the operator API and persistence-facing Slice 04-09
integration under `dataforge-Local/app/failureforge/`.

## Demo

```bash
bash scripts/run_sandbox_once.sh
bash scripts/verify_receipts.sh
bash scripts/replay_failure.sh sandbox/receipts/<receipt-id>.json
```
