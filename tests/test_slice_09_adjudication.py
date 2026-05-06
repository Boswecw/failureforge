"""Slice 09 — NeuroForge comparative adjudication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from failureforge.adjudication import run_provider_comparison_job
from failureforge.agents import (
    ChaosAgent,
    ClassificationAgent,
    EdgeCaseAgent,
    MutationAgent,
    ReproductionAgent,
)
from failureforge.clustering import build_clusters
from failureforge.runtime.sandbox import SandboxRunner
from failureforge.validation import (
    apply_receipt_hash,
    validate_model_adjudication_receipt,
    validate_neuroforge_adjudication_report,
    verify_model_adjudication_hash,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_CREATED = "2026-05-04T15:00:00Z"


def _receipt(
    *,
    receipt_id: str,
    failure_case_id: str,
    classification: str,
    severity: str,
    reproducible: bool,
    agent_lane: str,
    actual_result: str = "duplicate input created a new record",
) -> dict:
    return apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": receipt_id,
            "failure_case_id": failure_case_id,
            "sandbox_run_id": "SR-adjudication",
            "target_repo": "example-repo",
            "target_ref": "demo",
            "classification": classification,
            "severity": severity,
            "expected_result": "existing result reused",
            "actual_result": actual_result,
            "reproducible": reproducible,
            "repro_command": f"./scripts/replay_failure.sh sandbox/receipts/{receipt_id}.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": _CREATED,
            "agent_lane": agent_lane,
        }
    )


def _cluster() -> dict:
    receipts = [
        _receipt(
            receipt_id="FHR-nf-1",
            failure_case_id="FC-0001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            agent_lane="edge_case",
        ),
        _receipt(
            receipt_id="FHR-nf-2",
            failure_case_id="FC-CLASS-FC-0001",
            classification="duplicate_replay",
            severity="critical",
            reproducible=True,
            agent_lane="classification",
        ),
    ]
    return build_clusters(receipts)[0]


def _verdict(
    provider_name: str,
    *,
    classification: str = "duplicate_replay",
    severity: str = "critical",
    confidence: float = 0.91,
) -> dict:
    return {
        "provider_name": provider_name,
        "model_id": "nf-local-1",
        "proposed_classification": classification,
        "proposed_severity": severity,
        "confidence": confidence,
        "rationale": "receipt evidence and cluster fingerprint support this label",
    }


def test_provider_comparison_emits_valid_model_receipts():
    report = run_provider_comparison_job(
        cluster=_cluster(),
        provider_results=[_verdict("openai"), _verdict("anthropic")],
        job_id="NFJ-test-confirmed",
        created_at=_CREATED,
    )

    validate_neuroforge_adjudication_report(report)
    assert report["adjudication_status"] == "confirmed"
    assert report["operator_review_required"] is False
    assert report["final_classification"] == "duplicate_replay"
    assert report["final_severity"] == "critical"

    assert len(report["model_receipts"]) == 2
    for receipt in report["model_receipts"]:
        validate_model_adjudication_receipt(receipt)
        verify_model_adjudication_hash(receipt)
        assert receipt["agrees_with_cluster_classification"] is True


def test_final_classification_stays_deterministic_when_providers_dispute_cluster():
    report = run_provider_comparison_job(
        cluster=_cluster(),
        provider_results=[
            _verdict("openai", classification="missing_field", severity="high"),
            _verdict("anthropic", classification="missing_field", severity="high"),
        ],
        job_id="NFJ-test-disputed",
        created_at=_CREATED,
    )

    assert report["provider_consensus_classification"] == "missing_field"
    assert report["adjudication_status"] == "cluster_disputed"
    assert report["operator_review_required"] is True
    assert report["summary"]["cluster_disputed_by_provider_consensus"] is True
    assert report["final_classification"] == "duplicate_replay"
    assert report["deterministic_rule"] == "cluster_evidence_wins_over_provider_votes_v1"


def test_provider_disagreement_is_preserved_without_changing_final_classification():
    report = run_provider_comparison_job(
        cluster=_cluster(),
        provider_results=[
            _verdict("openai", classification="duplicate_replay", severity="critical"),
            _verdict("anthropic", classification="bad_path", severity="high"),
        ],
        job_id="NFJ-test-no-consensus",
        created_at=_CREATED,
    )

    assert report["provider_consensus_classification"] == "no_consensus"
    assert report["adjudication_status"] == "provider_disagreement"
    assert report["summary"]["provider_disagreement_count"] == 1
    assert report["operator_review_required"] is True
    assert report["final_classification"] == "duplicate_replay"


def test_provider_comparison_requires_two_unique_provider_model_pairs():
    with pytest.raises(ValueError, match="at least two"):
        run_provider_comparison_job(
            cluster=_cluster(),
            provider_results=[_verdict("openai")],
            job_id="NFJ-test-one",
            created_at=_CREATED,
        )

    with pytest.raises(ValueError, match="unique provider/model"):
        run_provider_comparison_job(
            cluster=_cluster(),
            provider_results=[_verdict("openai"), _verdict("openai")],
            job_id="NFJ-test-dup",
            created_at=_CREATED,
        )


def test_full_lane_cluster_can_be_neuroforge_adjudicated(tmp_path: Path):
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
    result = runner.run(agents=agents, sandbox_run_id="SR-adjudication-e2e")
    receipts = [json.loads(Path(p).read_text()) for p in result["receipt_paths"]]
    cluster = next(c for c in build_clusters(receipts) if c["classification"] == "duplicate_replay")

    report = run_provider_comparison_job(
        cluster=cluster,
        provider_results=[_verdict("openai"), _verdict("anthropic")],
        job_id="NFJ-test-e2e",
        created_at=_CREATED,
    )
    validate_neuroforge_adjudication_report(report)
    assert report["final_classification"] == cluster["classification"]
    assert {r["provider_name"] for r in report["model_receipts"]} == {
        "openai",
        "anthropic",
    }
