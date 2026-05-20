"""Slice 10 governance reconciliation tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from failureforge.validation import apply_receipt_hash

_ROOT = Path(__file__).resolve().parents[1]
_ECOSYSTEM = _ROOT.parent
_DATAFORGE_LOCAL = _ECOSYSTEM / "dataforge-Local"
if str(_DATAFORGE_LOCAL) not in sys.path:
    sys.path.insert(0, str(_DATAFORGE_LOCAL))


def _run() -> dict:
    return {
        "schema_version": "SandboxRun.v1",
        "sandbox_run_id": "SR-idempotency",
        "target_repo": "example-repo",
        "source_ref": "local",
        "workspace_path": "sandbox/workspaces/SR-idempotency/example-repo",
        "agent_lanes": ["edge_case"],
        "started_at": "2026-05-06T17:34:20Z",
        "completed_at": "2026-05-06T17:34:26Z",
        "status": "completed",
    }


def _case() -> dict:
    return {
        "schema_version": "FailureCase.v1",
        "failure_case_id": "FC-idempotency",
        "target_repo": "example-repo",
        "target_area": "registry_scan",
        "invariant": "Duplicate input must not create duplicate canonical records.",
        "attack_type": "duplicate_replay",
        "attack_description": "Replay same request.",
        "expected_result": "Existing result reused.",
        "agent_lane": "edge_case",
        "created_at": "2026-05-06T17:34:26Z",
    }


def _receipt() -> dict:
    return apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-idempotency",
            "failure_case_id": "FC-idempotency",
            "sandbox_run_id": "SR-idempotency",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": "critical",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate input created a new record.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-idempotency.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-06T17:34:26Z",
            "agent_lane": "edge_case",
        }
    )


def _service():
    from app.failureforge.service import (
        FailureForgeService,
        WriteAccepted,
        WriteRejected,
    )

    return FailureForgeService(), WriteAccepted, WriteRejected


def test_dataforge_same_receipt_id_same_hash_is_accepted_successfully():
    svc, WriteAccepted, _ = _service()
    svc.ingest_run(_run())
    svc.ingest_case(_case())
    receipt = _receipt()

    first = svc.ingest_receipt(receipt)
    second = svc.ingest_receipt(receipt)

    assert isinstance(first, WriteAccepted)
    assert isinstance(second, WriteAccepted)
    assert second.record["receipt_hash"] == receipt["receipt_hash"]


def test_dataforge_same_receipt_id_different_valid_hash_is_rejected_immutable():
    svc, WriteAccepted, WriteRejected = _service()
    svc.ingest_run(_run())
    svc.ingest_case(_case())
    receipt = _receipt()
    assert isinstance(svc.ingest_receipt(receipt), WriteAccepted)

    tampered = dict(receipt)
    tampered["actual_result"] = "TAMPERED but re-sealed"
    tampered = apply_receipt_hash(tampered)
    result = svc.ingest_receipt(tampered)

    assert isinstance(result, WriteRejected)
    assert result.error_class == "receipt_immutable"
    assert result.http_status == 409


def test_dataforge_transport_failure_does_not_delete_local_artifacts(tmp_path: Path):
    from failureforge.persistence import DataForgeFailureForgeClient, PushOutcome

    sandbox = tmp_path / "sandbox"
    run_dir = sandbox / "runs" / "SR-s10-offline"
    receipts_dir = sandbox / "receipts"
    run_dir.mkdir(parents=True)
    receipts_dir.mkdir(parents=True)
    run = _run()
    run["sandbox_run_id"] = "SR-s10-offline"
    run_dir.joinpath("sandbox_run.json").write_text(json.dumps(run), encoding="utf-8")
    receipt = _receipt()
    receipt["sandbox_run_id"] = "SR-s10-offline"
    receipt["failure_case_id"] = "FC-0001"
    receipt = apply_receipt_hash(receipt)
    receipts_dir.joinpath("FHR-s10-offline.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    bad = DataForgeFailureForgeClient(base_url="http://127.0.0.1:1", timeout_s=0.2)
    try:
        summary = bad.push_run_bundle_from_disk(
            run_id="SR-s10-offline",
            sandbox_root=sandbox,
        )
    finally:
        bad.close()

    assert summary.run is not None
    assert summary.run.outcome == PushOutcome.transport_failure
    assert list((sandbox / "receipts").glob("FHR-*.json"))


def test_failurecase_schema_did_not_gain_new_attack_family():
    schema = json.loads((_ROOT / "schemas/FailureCase.v1.schema.json").read_text())
    assert schema["properties"]["attack_type"]["enum"] == [
        "state_failure",
        "duplicate_replay",
        "missing_field",
        "unknown_enum",
        "bad_path",
        "bad_unicode",
        "malformed_input",
        "boundary",
    ]


def test_governance_docs_state_failureforge_role():
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    system = (_ROOT / "doc/system/00-purpose.md").read_text(encoding="utf-8")

    assert "Sandbox-only" in readme or "sandbox-only" in readme
    assert "may not mutate canonical repositories" in system
    assert "may not approve repair" in system


def test_slice_10_required_files_exist():
    required = [
        "pyproject.toml",
        "scripts/ci_gate.sh",
        "scripts/verify_no_canonical_mutation.sh",
        "doc/system/BUILD.sh",
        "doc/FFGSYSTEM.md",
        "schemas/FailureScore.v2.schema.json",
        "schemas/FailureForgeToERAExport.v1.schema.json",
        "schemas/FailureForgeAARSeed.v1.schema.json",
    ]
    missing = [p for p in required if not (_ROOT / p).exists()]
    assert missing == []
