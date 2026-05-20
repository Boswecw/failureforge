"""Centipede — deterministic root-cause clustering.

Receipts cluster on ``cluster_fingerprint``:

    sha256(target_repo + "|" + classification + "|" + attack_family + "|" + invariant)

The attack_family is a normalized form of the underlying attack_type so
lane-tagged receipts (FC-REPRO-, FC-CLASS-, FC-MUTATION-, FC-CHAOS-) cluster
with the canonical edge-case receipt that targets the same invariant.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from failureforge.validation import (
    validate_fix_cluster_report,
    validate_root_cause_cluster,
)

_LANE_PREFIXES = ("FC-REPRO-", "FC-CLASS-", "FC-MUTATION-", "FC-CHAOS-")

_ATTACK_FAMILY_BY_CLASSIFICATION: dict[str, str] = {
    "duplicate_replay": "duplicate_replay",
    "missing_field": "input_contract",
    "unknown_enum": "input_contract",
    "bad_path": "path_safety",
    "bad_unicode": "input_sanitisation",
    "malformed_input": "input_validation",
    "state_failure": "state_invariant",
    "boundary": "boundary",
    "no_failure_observed": "no_failure_observed",
}

_DEFAULT_RECOMMENDED_FIX: dict[str, str] = {
    "duplicate_replay": "enforce idempotency on the request key (existing-result reuse).",
    "missing_field": "validate required fields at the registry boundary; reject with a typed error.",
    "unknown_enum": "validate enums at the boundary against the canonical set.",
    "bad_path": "reject paths containing `..` or absolute escapes; canonicalize before write.",
    "bad_unicode": "strip or reject control characters; assert NFC after normalisation.",
    "malformed_input": "type-check input shape at the boundary; raise a typed error.",
    "state_failure": "investigate the divergence: actual_result must match invariant.",
    "no_failure_observed": "no fix needed; case may be promoted into the regression gate.",
}

_ROOT_CAUSE_LABEL: dict[str, str] = {
    "duplicate_replay": "unbounded_growth",
    "missing_field": "input_contract_break",
    "unknown_enum": "input_contract_break",
    "bad_path": "path_traversal",
    "bad_unicode": "input_sanitisation",
    "malformed_input": "input_validation",
    "state_failure": "state_invariant",
    "no_failure_observed": "no_failure_observed",
}

_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def logical_attack_id(receipt: dict[str, Any]) -> str:
    fid: str = receipt["failure_case_id"]
    for prefix in _LANE_PREFIXES:
        if fid.startswith(prefix):
            stripped = fid[len(prefix) :]
            return stripped if stripped.startswith("FC-") else fid
    return fid


def _attack_family(receipt: dict[str, Any]) -> str:
    return _ATTACK_FAMILY_BY_CLASSIFICATION.get(receipt["classification"], "unknown")


def _normalised_invariant(receipt: dict[str, Any]) -> str:
    """Receipts don't carry invariant text directly. We derive a stable
    invariant key from the classification alone for the example target;
    a richer implementation would join receipts to their FailureCase row."""
    return _ROOT_CAUSE_LABEL.get(receipt["classification"], "unknown")


def cluster_fingerprint(receipt: dict[str, Any]) -> str:
    """Deterministic root-cause fingerprint for a receipt."""
    parts = [
        receipt["target_repo"],
        receipt["classification"],
        _attack_family(receipt),
        _normalised_invariant(receipt),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def _ready_for_gate(group: list[dict[str, Any]]) -> bool:
    """A cluster is ready for a regression gate when at least one of its
    receipts is reproducible and is not a no_failure_observed signal."""
    return any(
        r.get("reproducible") and r["classification"] != "no_failure_observed"
        for r in group
    )


def _dominant_severity(severity_distribution: Counter[str]) -> str:
    if not severity_distribution:
        return "info"
    return max(severity_distribution, key=lambda s: _SEVERITY_RANK.get(s, 0))


def build_clusters(
    receipts: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group receipts into RootCauseCluster.v1 records.

    Source disagreement is preserved on each cluster as:
    - ``severity_distribution``: counts per severity across members
    - ``actual_result_distribution``: counts per distinct actual_result string

    The dominant severity is the highest-ranked severity present (so a single
    critical signal in a mostly-info cluster still escalates the cluster) —
    but the full distribution is preserved on the record for operator review.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in receipts:
        groups.setdefault(cluster_fingerprint(r), []).append(r)

    clusters: list[dict[str, Any]] = []
    for fingerprint, group in groups.items():
        sample = group[0]
        severity_dist = Counter(r.get("severity", "info") for r in group)
        actual_dist = Counter(r.get("actual_result", "") for r in group)
        lanes = sorted({r.get("agent_lane") for r in group if r.get("agent_lane")})
        if not lanes:
            lanes = ["edge_case"]
        first_seen = min(r["created_at"] for r in group)
        last_seen = max(r["created_at"] for r in group)
        cluster_id = _stable_id(
            "RC", sample["target_repo"], sample["classification"], fingerprint[:16]
        )
        cluster: dict[str, Any] = {
            "schema_version": "RootCauseCluster.v1",
            "cluster_id": cluster_id,
            "target_repo": sample["target_repo"],
            "classification": sample["classification"],
            "attack_family": _attack_family(sample),
            "invariant": _normalised_invariant(sample),
            "cluster_fingerprint": fingerprint,
            "root_cause_label": _ROOT_CAUSE_LABEL.get(
                sample["classification"], "unknown"
            ),
            "member_receipts": sorted(r["receipt_id"] for r in group),
            "member_count": len(group),
            "lanes": lanes,
            "lane_agreement": len(lanes),
            "dominant_severity": _dominant_severity(severity_dist),
            "severity_distribution": dict(severity_dist),
            "actual_result_distribution": dict(actual_dist),
            "reproducible_count": sum(1 for r in group if r.get("reproducible")),
            "first_seen_at": first_seen,
            "last_seen_at": last_seen,
            "status": "open",
            "representative_recommended_fix": _DEFAULT_RECOMMENDED_FIX.get(
                sample["classification"], "investigate; case requires manual triage."
            ),
            "ready_for_gate": _ready_for_gate(group),
        }
        validate_root_cause_cluster(cluster)
        clusters.append(cluster)

    clusters.sort(
        key=lambda c: (
            -_SEVERITY_RANK.get(c["dominant_severity"], 0),
            -c["lane_agreement"],
            -c["member_count"],
            c["cluster_id"],
        )
    )
    return clusters


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def build_fix_cluster_report(
    *,
    target_repo: str,
    receipts: Iterable[dict[str, Any]],
    report_id: str | None = None,
) -> dict[str, Any]:
    receipts_list = list(receipts)
    clusters = build_clusters(receipts_list)
    open_clusters = [c for c in clusters if c["status"] == "open"]
    ready = [c for c in clusters if c.get("ready_for_gate")]
    summary: dict[str, Any] = {
        "total_clusters": len(clusters),
        "open_clusters": len(open_clusters),
        "ready_for_gate_clusters": len(ready),
    }
    if clusters:
        summary["top_severity"] = clusters[0]["dominant_severity"]
        summary["top_recommended_fix"] = clusters[0]["representative_recommended_fix"]
    body = {
        "schema_version": "FixClusterReport.v1",
        "report_id": report_id or _stable_id("FCR", target_repo, _utc_now()),
        "target_repo": target_repo,
        "generated_at": _utc_now(),
        "clusters": clusters,
        "summary": summary,
    }
    validate_fix_cluster_report(body)
    return body


def render_fix_cluster_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Fix-Cluster Report",
        "",
        "## Summary",
        "",
        f"- Target repo: `{report['target_repo']}`",
        f"- Total clusters: {report['summary']['total_clusters']}",
        f"- Open clusters: {report['summary']['open_clusters']}",
        f"- Ready-for-gate clusters: {report['summary']['ready_for_gate_clusters']}",
    ]
    if "top_severity" in report["summary"]:
        lines.append(f"- Top severity: {report['summary']['top_severity']}")
        lines.append(f"- Top recommended fix: {report['summary']['top_recommended_fix']}")
    lines.extend(["", "## Clusters", ""])
    for c in report["clusters"]:
        lines.append(
            f"### {c['cluster_id']}  [{c['dominant_severity'].upper()}]  {c['classification']}"
        )
        lines.append("")
        lines.append(f"- Root cause: {c['root_cause_label']}")
        lines.append(f"- Attack family: {c['attack_family']}")
        lines.append(f"- Members: {c['member_count']}")
        lines.append(
            f"- Cross-agent agreement: {c['lane_agreement']} lane(s) ({', '.join(c['lanes'])})"
        )
        lines.append(f"- Severity distribution: {c['severity_distribution']}")
        if len(c["actual_result_distribution"]) > 1:
            lines.append("- Source disagreement on `actual_result`:")
            for text, count in c["actual_result_distribution"].items():
                lines.append(f"    - ({count}x) {text}")
        lines.append(f"- Recommended fix: {c['representative_recommended_fix']}")
        lines.append(f"- Ready for gate: {'yes' if c.get('ready_for_gate') else 'no'}")
        lines.append(f"- Receipts: {', '.join(c['member_receipts'])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
