        # failureforge - Compiled System Reference

        **Designation:** FFG
        **Document role:** Canonical compiled technical reference for failureforge
        **Source:** `doc/system/`
        **Build command:** `bash doc/system/BUILD.sh`
        **Document version:** 2.0 (2026-06-22) - canonical compliance migration
        **Protocol:** BDS Documentation Protocol v2.0; BDS Repo Documentation System Canonical Compliance Standard

        > **Generated artifact warning:** `doc/FFGSYSTEM.md` is assembled output. Edit
        > the source modules under `doc/system/` and rebuild. Hand edits to the
        > compiled artifact are overwritten by the next build.

        Assembly contract:

        - Command: `bash doc/system/BUILD.sh`
        - Validation: `bash doc/system/validate_snapshots.sh` runs during assembly
        - Primary output: `doc/FFGSYSTEM.md`

        This `doc/system/` tree is the canonical source of truth for failureforge. It uses
        explicit **truth classes**: canonical facts define repo role, authority
        boundaries, contract behavior, runtime behavior, and verification doctrine;
        snapshot facts are dated, audit-derived counts and current implementation
        inventory that may drift between audits.

        | Part | File | Contents |
        | --- | --- | --- |
        | §1 | `00_overview/00-purpose.md` | 00 Purpose |
| §2 | `00_overview/10-current-architecture.md` | 10 Current Architecture |
| §3 | `10_service-contract/20-contracts.md` | 20 Contracts |
| §4 | `20_runtime/30-runtime-boundary.md` | Runtime Boundary |
| §5 | `30_dependencies/30-integration-boundaries.md` | 30 Integration Boundaries |
| §6 | `40_governance/40-governance.md` | Governance |
| §7 | `50_operations/40-verification-gates.md` | 40 Verification Gates |
| §8 | `99_appendices/90-appendices.md` | Appendices |

        ## Quick Assembly

        ```bash
        bash doc/system/BUILD.sh
        ```

---

# 00 Purpose

FailureForge is a sandbox-only failure-harvesting subsystem for Forge.

It may create controlled failure probes, durable evidence, ranked hardening
reports, root-cause clusters, advisory adjudication records, and governed
promotion candidates.

It may not mutate canonical repositories, may not approve repair, may not
bypass operator review, may not let model votes overwrite deterministic
evidence, and may not promote unverified results as truth.

---

# 10 Current Architecture

FailureForge runs attacks only against copied workspaces under `sandbox/`.
The canonical demo target lives under `sandbox-targets/example-repo/` and is
protected by explicit hash checks.

The current implementation includes:

- Failure case, receipt, sandbox run, and hardening report contracts.
- Immutable receipt hashes and validation gates.
- Replay helpers for deterministic evidence checks.
- DataForge Local push client semantics for accepted, rejected, and transport
  failure outcomes.
- Operator approval and SMITH promotion-candidate handoff boundaries.
- Multi-lane failure agents.
- Centipede root-cause clustering.
- NeuroForge comparative adjudication where model votes remain advisory.
- Target adapter guards for explicit, copy-only expansion beyond the demo
  target.
- CLI target-source gating so non-default canonical source paths require a
  validated `TargetAdapter.v1`.
- Adapter preflight enforcement for required commands and forbidden
  canonical-source paths.
- Adapter-aware replay for receipts produced from external target sources.
- Replay command context capture for adapter-backed target-source receipts.
- Per-run canonical source fingerprinting in `SandboxRun.v1`.
- Fail-closed canonical mutation handling before receipt files are accepted.
- CLI canonical mutation failures return exit code `5`.
- Replay canonical mutation failures return exit code `5` without replay JSON.
- Replay writes its own run artifact and checks canonical source hashes before
  and after replay execution.
- Replay mismatches mark replay run artifacts failed and write exit code `2`.
- Replay CLI validates receipt schema and hash before target-source lookup.
- Receipt verification reports malformed receipt JSON as a validation failure.
- CLI adapter file load failures return controlled validation errors.

---

# 20 Contracts

FailureForge keeps its local schemas under `schemas/`.

Current local contracts include:

- `FailureCase.v1`
- `FailureHarvestReceipt.v1`
- `SandboxRun.v1`
- `HardeningReport.v1`
- `ApprovalReceipt.v1`
- `PromotionCandidate.v1`
- `RootCauseCluster.v1`
- `FixClusterReport.v1`
- `ModelAdjudicationReceipt.v1`
- `NeuroForgeAdjudicationReport.v1`
- `FailureScore.v2`
- `FailureForgeToERAExport.v1`
- `FailureForgeAARSeed.v1`
- `TargetAdapter.v1`

Slice 10 bridge contracts are draft contracts owned locally by FailureForge
with intended future authority in `forge-contract-core`. They are read-only
artifacts and carry no mutation, repair, or approval authority.

`TargetAdapter.v1` is also a draft local contract. It must declare supported
attack families, copy strategy, forbidden paths, artifact capture roots, and a
canonical mutation guard before FailureForge expands to a new target.

`SandboxRun.v1` runner-produced records include canonical source hashes before
and after execution plus a mutation flag. Minimal historical run records remain
valid for compatibility.

---

# Runtime Boundary

**Document version:** 2.0 (2026-06-22) - canonical compliance migration

Runtime behavior for failureforge must be documented from executable repo truth. This chapter anchors the canonical runtime section without adding unverified behavior.

---

# 30 Integration Boundaries

FailureForge produces evidence. DataForge Local stores local durable records.
ForgeCommand presents operator review. SMITH governs repair/promotion handoff.
ERA consumes read-only evidence exports. AAR consumes read-only seed artifacts.

Boundary rules:

- DataForge same receipt ID and same hash is accepted as an idempotent success.
- DataForge same receipt ID and different valid hash is rejected as immutable.
- DataForge transport failure does not invalidate local artifacts.
- ERA exports must keep `safe_to_autofix=false`.
- AAR seeds are not AAR conclusions and must cite receipt evidence.
- SMITH promotion candidates require an operator approval receipt.
- NeuroForge provider votes are advisory and cannot rewrite cluster evidence.
- Target adapters are read-only execution boundaries; unsupported attack
  families fail before workspace copy.
- External target source paths require a matching adapter before sandbox
  execution can begin.
- Adapter preflight rejects missing required commands or forbidden source paths
  before workspace copy.
- External-source replay must use the same adapter guard as external-source
  sandbox execution.
- Adapter-backed receipts must carry the replay arguments needed to preserve
  target-source context.

---

# Governance

**Document version:** 2.0 (2026-06-22) - canonical compliance migration

Governance rules for failureforge must preserve integration boundaries, verification gates, and operator review before broadening authority.

---

# 40 Verification Gates

The local proof gate is `bash scripts/ci_gate.sh`.

It writes evidence under `reports/failureforge-verification/latest/` and runs:

- dependency import check
- `python3 -m pytest`
- sandbox demo run
- receipt schema/hash verification
- deterministic replay
- no-canonical-mutation verification
- target adapter schema and preflight tests
- external target-source adapter requirement tests
- adapter required-command and forbidden-source-path tests
- adapter-aware external-source replay tests
- replay command context tests for adapter-backed receipts
- canonical source fingerprint tests
- fail-closed canonical mutation tests
- CLI canonical mutation exit tests
- CLI replay canonical mutation exit tests
- replay canonical mutation guard tests
- replay mismatch artifact status tests
- CLI replay receipt validation tests
- verify-receipts malformed JSON tests
- CLI adapter load validation tests
- documentation assembly

Supporting commands:

- `bash scripts/verify_receipts.sh`
- `bash scripts/replay_failure.sh sandbox/receipts/<receipt>.json`
- `bash scripts/verify_no_canonical_mutation.sh`
- `bash doc/system/BUILD.sh`

---

# Appendices

**Document version:** 2.0 (2026-06-22) - canonical compliance migration

Appendices hold glossary, cross-reference, and historical notes for failureforge system documentation.
