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
