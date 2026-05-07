# FailureForge

Sandbox-only failure-harvesting subsystem and read-only governance evidence
bridge for Forge. Per the
`docs/plans/failureforge_repo_reconciled_plan_set` plan, this directory
implements Slices 01-22:

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
- **Slice 10** - Governance reconciliation, ERA/AAR read-only bridge
  contracts, and local proof gates.
- **Slice 11** - Target adapter guard contract for explicit, copy-only
  expansion beyond demo targets.
- **Slice 12** - External target source gate requiring a validated adapter
  before probing any non-default source path.
- **Slice 13** - Adapter preflight enforcement for required commands and
  forbidden canonical-source paths.
- **Slice 14** - Adapter-aware replay for external target-source receipts.
- **Slice 15** - Replay command context for adapter-backed target-source
  receipts.
- **Slice 16** - Per-run canonical source fingerprinting in `SandboxRun.v1`.
- **Slice 17** - Fail-closed canonical mutation handling before receipt writes.
- **Slice 18** - CLI canonical mutation exit handling for fail-closed runs.
- **Slice 19** - CLI replay canonical mutation exit handling.
- **Slice 20** - Runtime replay canonical mutation guard.
- **Slice 21** - Replay mismatch artifact status alignment.
- **Slice 22** - CLI replay receipt validation before target lookup.

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
- ERA exports and AAR seeds are read-only bridge artifacts; they cannot claim
  fixes, bypass operator review, or mark evidence safe to autofix.
- Target adapters declare supported attack families and canonical mutation
  guards before a non-demo target can be probed.
- Explicit target source paths require target adapters; the demo target path
  remains the only adapter-optional execution route.
- Adapter preflight blocks missing tools or forbidden source paths before any
  workspace copy.
- Replay can use adapter-backed external target sources and applies the same
  preflight guard before copying a replay workspace.
- Receipts from adapter-backed runs carry the target-source and adapter replay
  arguments needed to reproduce the same source context.
- Sandbox runs record canonical source hashes before and after execution.
- If canonical source hashes differ, the run fails with no accepted receipts.
- The CLI maps canonical source mutation failures to exit code `5`.
- Replay uses the same canonical mutation exit code and suppresses replay JSON
  after fail-closed mutation errors.
- Replay records its own run artifact and fails closed if canonical source
  hashes change during replay.
- Replay mismatch artifacts are marked failed and carry exit code `2`, matching
  the CLI result.
- Replay validates receipt schema and hash before resolving a target source.

## Layout

```
failureforge/
  schemas/                  # receipt, report, promotion, approval, cluster, adjudication contracts
  fixtures/{valid,invalid}/ # contract fixtures
  src/failureforge/
    agents/                 # edge_case, chaos, mutation, reproduction, classification
    adjudication/           # Slice 09 NeuroForge provider comparison
    clustering/centipede.py # Slice 08 root-cause clustering
    integrations/           # Slice 10 ERA export + AAR seed builders
    runtime/target_adapter.py # Slice 11 target adapter guard
    runtime/sandbox.py      # SandboxRunner: copies workspace, runs lanes, writes receipts
    runtime/replay.py       # Replay helper used by replay_failure.sh
    reporting/scorer.py     # Slice 03 ranking + HardeningReport generator
    validation/             # JSON Schema + receipt-hash validators
    cli.py                  # run-sandbox, replay, verify-receipts, morning-report
  tests/                    # pytest suite for Slices 01-22
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

DataForge Local owns the operator API and persistence-facing Slice 04-18
integration under `dataforge-Local/app/failureforge/`.

## Demo

```bash
bash scripts/run_sandbox_once.sh
bash scripts/verify_receipts.sh
bash scripts/replay_failure.sh sandbox/receipts/<receipt-id>.json
```
