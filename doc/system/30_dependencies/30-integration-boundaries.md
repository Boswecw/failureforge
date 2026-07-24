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
