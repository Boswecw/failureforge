"""Slice 08 — Centipede clustering acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

from failureforge.agents import (
    ChaosAgent,
    ClassificationAgent,
    EdgeCaseAgent,
    MutationAgent,
    ReproductionAgent,
)
from failureforge.clustering import (
    build_clusters,
    build_fix_cluster_report,
    cluster_fingerprint,
    logical_attack_id,
    render_fix_cluster_markdown,
)
from failureforge.runtime.sandbox import SandboxRunner
from failureforge.validation import (
    apply_receipt_hash,
    validate_fix_cluster_report,
    validate_root_cause_cluster,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _receipt(
    *,
    receipt_id: str,
    failure_case_id: str,
    classification: str,
    severity: str,
    reproducible: bool,
    agent_lane: str,
    actual_result: str = "y",
    target_repo: str = "example-repo",
    created_at: str = "2026-05-04T15:00:00Z",
) -> dict:
    return apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": receipt_id,
            "failure_case_id": failure_case_id,
            "sandbox_run_id": "SR-cluster",
            "target_repo": target_repo,
            "target_ref": "demo",
            "classification": classification,
            "severity": severity,
            "expected_result": "x",
            "actual_result": actual_result,
            "reproducible": reproducible,
            "repro_command": f"./scripts/replay_failure.sh sandbox/receipts/{receipt_id}.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": created_at,
            "agent_lane": agent_lane,
        }
    )


# ---- duplicate receipt grouping -----------------------------------------


def test_duplicate_receipts_collapse_into_one_cluster():
    receipts = [
        _receipt(
            receipt_id="FHR-c-1",
            failure_case_id="FC-0001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            agent_lane="edge_case",
        ),
        _receipt(
            receipt_id="FHR-c-2",
            failure_case_id="FC-REPRO-FC-0001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            agent_lane="reproduction",
        ),
        _receipt(
            receipt_id="FHR-c-3",
            failure_case_id="FC-CLASS-FC-0001",
            classification="duplicate_replay",
            severity="critical",
            reproducible=True,
            agent_lane="classification",
        ),
    ]
    clusters = build_clusters(receipts)
    assert len(clusters) == 1
    cluster = clusters[0]
    validate_root_cause_cluster(cluster)
    assert cluster["member_count"] == 3
    assert set(cluster["member_receipts"]) == {"FHR-c-1", "FHR-c-2", "FHR-c-3"}


# ---- root-cause cluster id ---------------------------------------------


def test_cluster_id_is_stable_per_target_and_fingerprint():
    a = _receipt(
        receipt_id="FHR-stable-1",
        failure_case_id="FC-0001",
        classification="duplicate_replay",
        severity="high",
        reproducible=True,
        agent_lane="edge_case",
    )
    b = _receipt(
        receipt_id="FHR-stable-2",
        failure_case_id="FC-0001",
        classification="duplicate_replay",
        severity="high",
        reproducible=True,
        agent_lane="edge_case",
        created_at="2026-05-05T10:00:00Z",
    )
    first = build_clusters([a])
    second = build_clusters([a, b])
    assert first[0]["cluster_id"] == second[0]["cluster_id"]
    assert first[0]["cluster_fingerprint"] == cluster_fingerprint(a)


# ---- source disagreement preserved -------------------------------------


def test_source_disagreement_on_severity_is_preserved():
    receipts = [
        _receipt(
            receipt_id="FHR-d-1",
            failure_case_id="FC-0001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            agent_lane="edge_case",
        ),
        _receipt(
            receipt_id="FHR-d-2",
            failure_case_id="FC-CLASS-FC-0001",
            classification="duplicate_replay",
            severity="critical",
            reproducible=True,
            agent_lane="classification",
        ),
    ]
    clusters = build_clusters(receipts)
    cluster = clusters[0]
    assert cluster["dominant_severity"] == "critical"
    assert cluster["severity_distribution"]["critical"] == 1
    assert cluster["severity_distribution"]["high"] == 1


def test_source_disagreement_on_actual_result_is_preserved():
    receipts = [
        _receipt(
            receipt_id="FHR-ar-1",
            failure_case_id="FC-0001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            agent_lane="edge_case",
            actual_result="duplicate input created a new record (size=2)",
        ),
        _receipt(
            receipt_id="FHR-ar-2",
            failure_case_id="FC-REPRO-FC-0001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            agent_lane="reproduction",
            actual_result="deterministic across 3 runs: duplicate input created a new record",
        ),
    ]
    clusters = build_clusters(receipts)
    cluster = clusters[0]
    assert len(cluster["actual_result_distribution"]) == 2
    md = render_fix_cluster_markdown(
        build_fix_cluster_report(target_repo="example-repo", receipts=receipts)
    )
    assert "Source disagreement on `actual_result`" in md


# ---- fix-cluster report -------------------------------------------------


def test_fix_cluster_report_validates_and_ranks_critical_first():
    receipts = [
        _receipt(
            receipt_id="FHR-rep-1",
            failure_case_id="FC-0001",
            classification="duplicate_replay",
            severity="critical",
            reproducible=True,
            agent_lane="classification",
        ),
        _receipt(
            receipt_id="FHR-rep-2",
            failure_case_id="FC-0004",
            classification="bad_path",
            severity="high",
            reproducible=True,
            agent_lane="edge_case",
        ),
    ]
    report = build_fix_cluster_report(target_repo="example-repo", receipts=receipts)
    validate_fix_cluster_report(report)
    assert report["clusters"][0]["dominant_severity"] == "critical"
    assert report["clusters"][0]["classification"] == "duplicate_replay"
    assert report["summary"]["ready_for_gate_clusters"] == 2
    md = render_fix_cluster_markdown(report)
    assert "# Fix-Cluster Report" in md
    assert "Recommended fix" in md


def test_logical_attack_id_strips_lane_prefixes():
    assert logical_attack_id({"failure_case_id": "FC-0001"}) == "FC-0001"
    assert logical_attack_id({"failure_case_id": "FC-REPRO-FC-0001"}) == "FC-0001"
    assert logical_attack_id({"failure_case_id": "FC-CLASS-FC-0001"}) == "FC-0001"


# ---- end-to-end against the demo target ---------------------------------


def test_full_lane_run_then_cluster(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    agents = [
        EdgeCaseAgent(target_repo="example-repo"),
        ChaosAgent(target_repo="example-repo"),
        MutationAgent(target_repo="example-repo"),
        ReproductionAgent(target_repo="example-repo", repeats=2),
        ClassificationAgent(target_repo="example-repo"),
    ]
    result = runner.run(agents=agents, sandbox_run_id="SR-cluster-e2e")
    receipts = [json.loads(Path(p).read_text()) for p in result["receipt_paths"]]

    report = build_fix_cluster_report(target_repo="example-repo", receipts=receipts)
    validate_fix_cluster_report(report)

    # The duplicate_replay cluster should agree across at least edge_case +
    # reproduction + classification.
    dup = next(
        c for c in report["clusters"] if c["classification"] == "duplicate_replay"
    )
    assert dup["lane_agreement"] >= 3
    assert {"edge_case", "reproduction", "classification"}.issubset(set(dup["lanes"]))
    assert dup["ready_for_gate"] is True
