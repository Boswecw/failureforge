"""Slice 24 CLI target adapter load validation tests."""

from __future__ import annotations

import json
from pathlib import Path

from failureforge.cli import main
from failureforge.validation import apply_receipt_hash


def _seed_receipt(path: Path) -> None:
    receipt = apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-s24-cli",
            "failure_case_id": "FC-0001",
            "sandbox_run_id": "SR-s24-cli",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": "high",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate created.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-s24-cli.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-07T00:00:00Z",
        }
    )
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def test_run_sandbox_cli_rejects_schema_invalid_adapter(tmp_path: Path, capsys):
    adapter_path = tmp_path / "adapter.json"
    adapter_path.write_text(
        json.dumps({"schema_version": "TargetAdapter.v1"}, indent=2),
        encoding="utf-8",
    )

    rc = main(
        [
            "run-sandbox",
            "--target",
            "example-repo",
            "--adapter",
            str(adapter_path),
            "--run-id",
            "SR-s24-adapter",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "invalid target adapter" in captured.err
    assert "adapter_id" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_replay_cli_rejects_missing_adapter_file(tmp_path: Path, capsys):
    receipt_path = tmp_path / "receipt.json"
    _seed_receipt(receipt_path)
    adapter_path = tmp_path / "missing-adapter.json"

    rc = main(["replay", str(receipt_path), "--adapter", str(adapter_path)])

    captured = capsys.readouterr()
    assert rc == 2
    assert "invalid target adapter" in captured.err
    assert str(adapter_path) in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
