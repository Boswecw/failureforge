"""FailureForge -> ERA read-only bridge artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from failureforge.validation import validate_failureforge_to_era_export


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _hash(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _receipt_ids(receipts: Iterable[dict[str, Any]]) -> list[str]:
    return sorted({r["receipt_id"] for r in receipts})


def _lane_summaries(classification: str) -> list[tuple[str, str]]:
    if classification == "duplicate_replay":
        return [
            ("accuracy", "Idempotency contract failure."),
            ("redundancy", "Duplicate canonical record risk."),
            ("efficiency", "Unbounded growth or retry cost risk."),
            ("cross_lane", "Shared invariant failure across ERA dimensions."),
        ]
    if classification in {"missing_field", "unknown_enum", "bad_path", "bad_unicode", "malformed_input", "state_failure"}:
        return [("accuracy", f"{classification} indicates boundary validation drift.")]
    if classification == "boundary":
        return [("cross_lane", "Boundary failure requires cross-system review.")]
    return [("accuracy", "No failure observed; retain as informational evidence.")]


def map_receipt_to_era_candidate(receipt: dict[str, Any], *, lane: str | None = None) -> dict[str, Any]:
    """Map one FailureHarvestReceipt into one read-only ERA candidate finding."""
    selected_lane, summary = (
        (lane, f"{receipt['classification']} evidence from FailureForge.")
        if lane is not None
        else _lane_summaries(receipt["classification"])[0]
    )
    return {
        "candidate_id": _stable_id(
            "ERA-FC", receipt["receipt_id"], selected_lane or "accuracy"
        ),
        "era_lane": selected_lane,
        "source_classification": receipt["classification"],
        "source_receipts": [receipt["receipt_id"]],
        "finding_summary": summary,
        "requires_operator_review": True,
        "safe_to_autofix": False,
        "claims_fix": False,
    }


def map_cluster_to_era_candidates(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    """Map one root-cause cluster into ERA lane candidates.

    The mapping preserves FailureForge classification and receipt IDs. It does
    not claim a fix or patch authority.
    """
    candidates: list[dict[str, Any]] = []
    for lane, summary in _lane_summaries(cluster["classification"]):
        candidates.append(
            {
                "candidate_id": _stable_id(
                    "ERA-FC", cluster["cluster_id"], lane, cluster["classification"]
                ),
                "era_lane": lane,
                "source_classification": cluster["classification"],
                "source_receipts": sorted(cluster["member_receipts"]),
                "finding_summary": summary,
                "requires_operator_review": True,
                "safe_to_autofix": False,
                "claims_fix": False,
            }
        )
    return candidates


def build_era_export(
    *,
    sandbox_run: dict[str, Any],
    hardening_report: dict[str, Any],
    receipts: Iterable[dict[str, Any]],
    clusters: Iterable[dict[str, Any]] = (),
    export_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    receipts_list = list(receipts)
    clusters_list = list(clusters)
    if not receipts_list:
        raise ValueError("ERA export requires at least one receipt")

    candidates: list[dict[str, Any]] = []
    for cluster in clusters_list:
        candidates.extend(map_cluster_to_era_candidates(cluster))
    if not candidates:
        candidates = [map_receipt_to_era_candidate(r) for r in receipts_list]

    body = {
        "schema_version": "FailureForgeToERAExport.v1",
        "export_id": export_id
        or _stable_id(
            "FFE",
            sandbox_run["sandbox_run_id"],
            hardening_report["report_id"],
            _hash(_receipt_ids(receipts_list))[:12],
        ),
        "target_repo": sandbox_run["target_repo"],
        "source_ref": sandbox_run["source_ref"],
        "sandbox_run_id": sandbox_run["sandbox_run_id"],
        "hardening_report_id": hardening_report["report_id"],
        "included_receipts": _receipt_ids(receipts_list),
        "included_clusters": sorted(c["cluster_id"] for c in clusters_list),
        "ranked_findings": hardening_report.get("ranked_findings", []),
        "era_candidate_findings": candidates,
        "read_only_invariant_status": {
            "safe_to_autofix": False,
            "requires_operator_review": True,
            "claims_fix": False,
            "preserves_failureforge_classification": True,
            "model_adjudication_is_advisory": True,
        },
        "artifact_hashes": {
            "sandbox_run": _hash(sandbox_run),
            "hardening_report": _hash(hardening_report),
            "receipts": _hash(receipts_list),
            "clusters": _hash(clusters_list),
        },
        "created_at": created_at or _utc_now(),
    }
    validate_failureforge_to_era_export(body)
    return body


def write_era_export(
    *,
    export: dict[str, Any],
    sandbox_root: Path,
) -> Path:
    validate_failureforge_to_era_export(export)
    out_dir = sandbox_root / "exports" / "era"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{export['export_id']}.json"
    path.write_text(json.dumps(export, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
