"""NeuroForge comparative adjudication.

Slice 09 records provider/model verdicts, but it does not let model votes
silently rewrite FailureForge's final classification. The final classification
and final severity are deterministic projections of the RootCauseCluster. The
provider comparison can confirm the cluster, flag provider disagreement, or
flag a disputed cluster for operator review.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from failureforge.validation import (
    apply_model_adjudication_hash,
    validate_model_adjudication_receipt,
    validate_neuroforge_adjudication_report,
    validate_root_cause_cluster,
)

_CLASSIFICATIONS = {
    "state_failure",
    "duplicate_replay",
    "missing_field",
    "unknown_enum",
    "bad_path",
    "bad_unicode",
    "malformed_input",
    "boundary",
    "no_failure_observed",
}

_SEVERITIES = {"critical", "high", "medium", "low", "info"}

_DETERMINISTIC_RULE = "cluster_evidence_wins_over_provider_votes_v1"


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def provider_result_hash(verdict: dict[str, Any]) -> str:
    """Hash the provider result fields used by the adjudication reducer."""
    normalised = _normalise_verdict(verdict)
    return hashlib.sha256(_canonical(normalised)).hexdigest()


def _normalise_verdict(verdict: dict[str, Any]) -> dict[str, Any]:
    required = {
        "provider_name",
        "model_id",
        "proposed_classification",
        "proposed_severity",
        "confidence",
        "rationale",
    }
    missing = sorted(required - set(verdict))
    if missing:
        raise ValueError(f"provider verdict missing required field(s): {', '.join(missing)}")

    classification = str(verdict["proposed_classification"])
    if classification not in _CLASSIFICATIONS:
        raise ValueError(f"unknown proposed_classification: {classification}")

    severity = str(verdict["proposed_severity"])
    if severity not in _SEVERITIES:
        raise ValueError(f"unknown proposed_severity: {severity}")

    try:
        confidence = float(verdict["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be a number between 0 and 1") from exc
    if confidence < 0 or confidence > 1:
        raise ValueError("confidence must be between 0 and 1")

    rationale = str(verdict["rationale"]).strip()
    if not rationale:
        raise ValueError("rationale must be non-empty")

    return {
        "provider_name": str(verdict["provider_name"]),
        "model_id": str(verdict["model_id"]),
        "proposed_classification": classification,
        "proposed_severity": severity,
        "confidence": confidence,
        "rationale": rationale,
    }


def build_model_adjudication_receipt(
    *,
    cluster: dict[str, Any],
    verdict: dict[str, Any],
    job_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_root_cause_cluster(cluster)
    normalised = _normalise_verdict(verdict)
    result_hash = provider_result_hash(normalised)
    body = {
        "schema_version": "ModelAdjudicationReceipt.v1",
        "adjudication_receipt_id": _stable_id(
            "MAR",
            job_id,
            cluster["cluster_id"],
            normalised["provider_name"],
            normalised["model_id"],
        ),
        "job_id": job_id,
        "cluster_id": cluster["cluster_id"],
        "target_repo": cluster["target_repo"],
        "provider_name": normalised["provider_name"],
        "model_id": normalised["model_id"],
        "proposed_classification": normalised["proposed_classification"],
        "proposed_severity": normalised["proposed_severity"],
        "confidence": normalised["confidence"],
        "agrees_with_cluster_classification": (
            normalised["proposed_classification"] == cluster["classification"]
        ),
        "agrees_with_cluster_severity": (
            normalised["proposed_severity"] == cluster["dominant_severity"]
        ),
        "rationale": normalised["rationale"],
        "evidence_receipts": sorted(cluster["member_receipts"]),
        "deterministic_inputs": {
            "cluster_classification": cluster["classification"],
            "cluster_dominant_severity": cluster["dominant_severity"],
            "cluster_fingerprint": cluster["cluster_fingerprint"],
            "cluster_member_count": cluster["member_count"],
            "cluster_ready_for_gate": bool(cluster.get("ready_for_gate")),
            "provider_result_hash": result_hash,
        },
        "created_at": created_at or _utc_now(),
    }
    sealed = apply_model_adjudication_hash(body)
    validate_model_adjudication_receipt(sealed)
    return sealed


def _consensus(values: Iterable[str]) -> str:
    counts = Counter(values)
    if not counts:
        return "no_consensus"
    winner, count = counts.most_common(1)[0]
    return winner if count > sum(counts.values()) / 2 else "no_consensus"


def _job_id_for(cluster: dict[str, Any], verdicts: list[dict[str, Any]]) -> str:
    hashes = sorted(provider_result_hash(v) for v in verdicts)
    return _stable_id("NFJ", cluster["cluster_id"], cluster["cluster_fingerprint"], *hashes)


def run_provider_comparison_job(
    *,
    cluster: dict[str, Any],
    provider_results: Iterable[dict[str, Any]],
    job_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_root_cause_cluster(cluster)
    verdicts = [_normalise_verdict(v) for v in provider_results]
    if len(verdicts) < 2:
        raise ValueError("provider comparison requires at least two provider verdicts")

    seen = {(v["provider_name"], v["model_id"]) for v in verdicts}
    if len(seen) != len(verdicts):
        raise ValueError("provider comparison requires unique provider/model pairs")

    issued_at = created_at or _utc_now()
    job = job_id or _job_id_for(cluster, verdicts)
    receipts = [
        build_model_adjudication_receipt(
            cluster=cluster, verdict=v, job_id=job, created_at=issued_at
        )
        for v in verdicts
    ]

    class_consensus = _consensus(r["proposed_classification"] for r in receipts)
    sev_consensus = _consensus(r["proposed_severity"] for r in receipts)
    provider_disagreements = sum(
        1
        for r in receipts
        if not r["agrees_with_cluster_classification"]
        or not r["agrees_with_cluster_severity"]
    )
    classification_disputed = (
        class_consensus != "no_consensus"
        and class_consensus != cluster["classification"]
    )
    severity_disputed = (
        sev_consensus != "no_consensus"
        and sev_consensus != cluster["dominant_severity"]
    )
    cluster_disputed = classification_disputed or severity_disputed
    no_provider_consensus = (
        class_consensus == "no_consensus" or sev_consensus == "no_consensus"
    )

    if cluster_disputed:
        status = "cluster_disputed"
    elif no_provider_consensus:
        status = "provider_disagreement"
    else:
        status = "confirmed"

    report = {
        "schema_version": "NeuroForgeAdjudicationReport.v1",
        "job_id": job,
        "target_repo": cluster["target_repo"],
        "cluster_id": cluster["cluster_id"],
        "cluster_fingerprint": cluster["cluster_fingerprint"],
        "provider_count": len(receipts),
        "provider_consensus_classification": class_consensus,
        "provider_consensus_severity": sev_consensus,
        "final_classification": cluster["classification"],
        "final_severity": cluster["dominant_severity"],
        "adjudication_status": status,
        "operator_review_required": status != "confirmed",
        "deterministic_rule": _DETERMINISTIC_RULE,
        "model_receipts": receipts,
        "summary": {
            "cluster_classification_confirmed": (
                class_consensus == cluster["classification"]
            ),
            "provider_disagreement_count": provider_disagreements,
            "cluster_disputed_by_provider_consensus": cluster_disputed,
        },
        "created_at": issued_at,
    }
    validate_neuroforge_adjudication_report(report)
    return report
