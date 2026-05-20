"""Slice 23 verify-receipts malformed JSON tests."""

from __future__ import annotations

import json
from pathlib import Path

from failureforge.cli import main
from failureforge.validation import apply_receipt_hash


def _seed_valid_receipt(path: Path) -> None:
    receipt = apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-s23-valid",
            "failure_case_id": "FC-0001",
            "sandbox_run_id": "SR-s23",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": "high",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate created.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-s23-valid.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-07T00:00:00Z",
        }
    )
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def test_verify_receipts_reports_malformed_json_without_traceback(
    monkeypatch, tmp_path: Path, capsys
):
    import failureforge.cli as cli

    receipts_dir = tmp_path / "sandbox" / "receipts"
    receipts_dir.mkdir(parents=True)
    _seed_valid_receipt(receipts_dir / "FHR-s23-valid.json")
    (receipts_dir / "FHR-s23-malformed.json").write_text(
        "{not json\n", encoding="utf-8"
    )
    monkeypatch.setattr(cli, "_failureforge_root", lambda: tmp_path)

    rc = main(["verify-receipts"])

    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert rc == 2
    assert summary["checked"] == 2
    assert len(summary["failures"]) == 1
    assert (
        summary["failures"][0]["receipt"] == "sandbox/receipts/FHR-s23-malformed.json"
    )
    assert "Expecting property name" in summary["failures"][0]["error"]
    assert "Traceback" not in captured.err
