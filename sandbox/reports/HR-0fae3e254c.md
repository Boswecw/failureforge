# Hardening Report

## Summary

- Target repo: `example-repo`
- Sandbox run: `SR-03b9c9ad73`
- Receipts produced: 6
- Reproducible failures: 6
- Top recommended fix: enforce idempotency on the request key (existing-result reuse).

## Ranked Findings

1. [HIGH] duplicate_replay (score=96)
   - Failure case: `FC-0001`
   - Reproducibility: reproducible
   - Blast radius: service
   - Frequency: 1
   - Fix complexity: small
   - Recommended fix: enforce idempotency on the request key (existing-result reuse).
   - Repro command: `./scripts/replay_failure.sh sandbox/receipts/FHR-f5a441a54a.json`
   - Receipts: FHR-f5a441a54a
   - Cross-agent agreement: 1 lane(s) (edge_case)
   - Ready for gate: yes

2. [INFO] no_failure_observed (score=33)
   - Failure case: `FC-0002`
   - Reproducibility: reproducible
   - Blast radius: unknown
   - Frequency: 1
   - Fix complexity: trivial
   - Recommended fix: no fix needed; case may be promoted into the regression gate.
   - Repro command: `./scripts/replay_failure.sh sandbox/receipts/FHR-7512f98828.json`
   - Receipts: FHR-7512f98828
   - Cross-agent agreement: 1 lane(s) (edge_case)
   - Ready for gate: no

3. [INFO] no_failure_observed (score=33)
   - Failure case: `FC-0003`
   - Reproducibility: reproducible
   - Blast radius: unknown
   - Frequency: 1
   - Fix complexity: trivial
   - Recommended fix: no fix needed; case may be promoted into the regression gate.
   - Repro command: `./scripts/replay_failure.sh sandbox/receipts/FHR-72a4e1f255.json`
   - Receipts: FHR-72a4e1f255
   - Cross-agent agreement: 1 lane(s) (edge_case)
   - Ready for gate: no

4. [INFO] no_failure_observed (score=33)
   - Failure case: `FC-0004`
   - Reproducibility: reproducible
   - Blast radius: unknown
   - Frequency: 1
   - Fix complexity: trivial
   - Recommended fix: no fix needed; case may be promoted into the regression gate.
   - Repro command: `./scripts/replay_failure.sh sandbox/receipts/FHR-757b6c068d.json`
   - Receipts: FHR-757b6c068d
   - Cross-agent agreement: 1 lane(s) (edge_case)
   - Ready for gate: no

5. [INFO] no_failure_observed (score=33)
   - Failure case: `FC-0005`
   - Reproducibility: reproducible
   - Blast radius: unknown
   - Frequency: 1
   - Fix complexity: trivial
   - Recommended fix: no fix needed; case may be promoted into the regression gate.
   - Repro command: `./scripts/replay_failure.sh sandbox/receipts/FHR-cd5493222c.json`
   - Receipts: FHR-cd5493222c
   - Cross-agent agreement: 1 lane(s) (edge_case)
   - Ready for gate: no

6. [INFO] no_failure_observed (score=33)
   - Failure case: `FC-0006`
   - Reproducibility: reproducible
   - Blast radius: unknown
   - Frequency: 1
   - Fix complexity: trivial
   - Recommended fix: no fix needed; case may be promoted into the regression gate.
   - Repro command: `./scripts/replay_failure.sh sandbox/receipts/FHR-77c2f09406.json`
   - Receipts: FHR-77c2f09406
   - Cross-agent agreement: 1 lane(s) (edge_case)
   - Ready for gate: no
