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
