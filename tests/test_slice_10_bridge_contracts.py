"""Slice 10 bridge contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from failureforge.clustering import build_clusters
from failureforge.integrations import (
    build_aar_seed,
    build_era_export,
    map_cluster_to_era_candidates,
    write_aar_seed,
    write_era_export,
)
from failureforge.reporting.scorer import build_hardening_report
from failureforge.validation import (
    SchemaValidationError,
    apply_receipt_hash,
    validate_failure_score_v2,
    validate_failureforge_aar_seed,
    validate_failureforge_to_era_export,
)


_ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads((_ROOT / path).read_text(encoding="utf-8"))


def _receipt(
    *,
    receipt_id: str = "FHR-s10-1",
    failure_case_id: str = "FC-0001",
    severity: str = "critical",
    agent_lane: str = "classification",
) -> dict:
    return apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": receipt_id,
            "failure_case_id": failure_case_id,
            "sandbox_run_id": "SR-s10",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": severity,
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate input created a new record.",
            "reproducible": True,
            "repro_command": f"./scripts/replay_failure.sh sandbox/receipts/{receipt_id}.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-06T17:34:26Z",
            "agent_lane": agent_lane,
        }
    )


def _sandbox_run() -> dict:
    return {
        "schema_version": "SandboxRun.v1",
        "sandbox_run_id": "SR-s10",
        "target_repo": "example-repo",
        "source_ref": "local",
        "workspace_path": "sandbox/workspaces/SR-s10/example-repo",
        "agent_lanes": ["classification"],
        "started_at": "2026-05-06T17:34:20Z",
        "completed_at": "2026-05-06T17:34:26Z",
        "status": "completed",
    }


def test_valid_bridge_fixtures_validate():
    validate_failure_score_v2(_load("fixtures/valid/FailureScore.v2.valid.json"))
    validate_failureforge_to_era_export(
        _load("fixtures/valid/FailureForgeToERAExport.v1.valid.json")
    )
    validate_failureforge_aar_seed(
        _load("fixtures/valid/FailureForgeAARSeed.v1.valid.json")
    )


@pytest.mark.parametrize(
    ("fixture", "validator"),
    [
        (
            "fixtures/invalid/FailureScore.v2.missing-score-inputs-hash.json",
            validate_failure_score_v2,
        ),
        (
            "fixtures/invalid/FailureForgeToERAExport.v1.autofix-true.json",
            validate_failureforge_to_era_export,
        ),
        (
            "fixtures/invalid/FailureForgeAARSeed.v1.missing-receipts.json",
            validate_failureforge_aar_seed,
        ),
    ],
)
def test_invalid_bridge_fixtures_fail(fixture: str, validator):
    with pytest.raises(SchemaValidationError):
        validator(_load(fixture))


def test_era_export_builder_preserves_classification_and_blocks_autofix(tmp_path: Path):
    receipts = [
        _receipt(receipt_id="FHR-s10-1", severity="high", agent_lane="edge_case"),
        _receipt(
            receipt_id="FHR-s10-2",
            failure_case_id="FC-CLASS-FC-0001",
            severity="critical",
            agent_lane="classification",
        ),
    ]
    clusters = build_clusters(receipts)
    report = build_hardening_report(
        sandbox_run_id="SR-s10",
        target_repo="example-repo",
        receipts=receipts,
    )

    export = build_era_export(
        sandbox_run=_sandbox_run(),
        hardening_report=report,
        receipts=receipts,
        clusters=clusters,
        created_at="2026-05-06T17:34:26Z",
    )
    validate_failureforge_to_era_export(export)
    assert export["read_only_invariant_status"]["safe_to_autofix"] is False
    assert export["read_only_invariant_status"]["claims_fix"] is False
    assert {c["era_lane"] for c in export["era_candidate_findings"]} == {
        "accuracy",
        "redundancy",
        "efficiency",
        "cross_lane",
    }
    assert {
        c["source_classification"] for c in export["era_candidate_findings"]
    } == {"duplicate_replay"}
    assert all(c["safe_to_autofix"] is False for c in export["era_candidate_findings"])

    path = write_era_export(export=export, sandbox_root=tmp_path)
    assert path.exists()


def test_aar_seed_builder_preserves_evidence_and_disagreement(tmp_path: Path):
    receipts = [
        _receipt(receipt_id="FHR-aar-1", severity="high", agent_lane="edge_case"),
        _receipt(
            receipt_id="FHR-aar-2",
            failure_case_id="FC-CLASS-FC-0001",
            severity="critical",
            agent_lane="classification",
        ),
    ]
    cluster = build_clusters(receipts)[0]

    seed = build_aar_seed(
        cluster=cluster,
        receipts=receipts,
        sandbox_run_id="SR-s10",
        source_ref="local",
        created_at="2026-05-06T17:34:26Z",
    )
    validate_failureforge_aar_seed(seed)
    assert seed["evidence_receipts"] == sorted(cluster["member_receipts"])
    assert seed["source_disagreement"]["preserved"] is True
    assert seed["operator_review_required"] is True
    assert seed["deterministic_status"] == "reproducible"

    path = write_aar_seed(seed=seed, sandbox_root=tmp_path)
    assert path.exists()


def test_cluster_mapping_never_claims_fix_authority():
    cluster = build_clusters([_receipt()])[0]
    candidates = map_cluster_to_era_candidates(cluster)

    assert candidates
    assert all(c["requires_operator_review"] is True for c in candidates)
    assert all(c["safe_to_autofix"] is False for c in candidates)
    assert all(c["claims_fix"] is False for c in candidates)
