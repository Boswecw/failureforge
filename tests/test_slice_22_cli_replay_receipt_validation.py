"""Slice 22 CLI replay receipt validation tests."""

from __future__ import annotations

import json
from pathlib import Path

from failureforge.cli import main
from failureforge.validation import apply_receipt_hash


def _valid_receipt() -> dict:
    return apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-s22-cli",
            "failure_case_id": "FC-0001",
            "sandbox_run_id": "SR-s22-cli",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": "high",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate created.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-s22-cli.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-07T00:00:00Z",
        }
    )


def _write_receipt(path: Path, receipt: dict) -> None:
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def test_cli_replay_rejects_tampered_receipt_hash(tmp_path: Path, capsys):
    receipt_path = tmp_path / "tampered.json"
    receipt = _valid_receipt()
    receipt["actual_result"] = "Changed after hash."
    _write_receipt(receipt_path, receipt)

    rc = main(["replay", str(receipt_path)])

    captured = capsys.readouterr()
    assert rc == 2
    assert "invalid replay receipt" in captured.err
    assert "receipt_hash mismatch" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_cli_replay_rejects_schema_invalid_receipt_before_target_lookup(
    tmp_path: Path, capsys
):
    receipt_path = tmp_path / "missing-target.json"
    receipt = _valid_receipt()
    receipt.pop("target_repo")
    _write_receipt(receipt_path, apply_receipt_hash(receipt))

    rc = main(["replay", str(receipt_path)])

    captured = capsys.readouterr()
    assert rc == 2
    assert "invalid replay receipt" in captured.err
    assert "target_repo" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_cli_replay_rejects_malformed_json_receipt(tmp_path: Path, capsys):
    receipt_path = tmp_path / "malformed.json"
    receipt_path.write_text("{not json\n", encoding="utf-8")

    rc = main(["replay", str(receipt_path)])

    captured = capsys.readouterr()
    assert rc == 2
    assert "invalid replay receipt" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
