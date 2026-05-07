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
