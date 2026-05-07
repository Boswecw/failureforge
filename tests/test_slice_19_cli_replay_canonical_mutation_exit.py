"""Slice 19 CLI replay canonical-mutation exit tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from failureforge.cli import main
from failureforge.runtime import CanonicalSourceMutationError
from failureforge.validation import apply_receipt_hash


def _seed_receipt(path: Path) -> None:
    receipt = apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-s19-cli",
            "failure_case_id": "FC-0001",
            "sandbox_run_id": "SR-s19-cli",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": "high",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate created.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-s19-cli.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-07T00:00:00Z",
        }
    )
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def _raise_canonical_mutation(**kwargs: Any) -> None:
    raise CanonicalSourceMutationError(
        {
            "canonical_source_hash_before": "0" * 64,
            "canonical_source_hash_after": "1" * 64,
        }
    )


def test_replay_cli_returns_5_for_canonical_mutation(
    monkeypatch, tmp_path: Path, capsys
):
    import failureforge.cli as cli

    receipt_path = tmp_path / "receipt.json"
    _seed_receipt(receipt_path)
    monkeypatch.setattr(cli, "replay_receipt", _raise_canonical_mutation)

    rc = main(["replay", str(receipt_path)])

    captured = capsys.readouterr()
    assert rc == 5
    assert "canonical source mutated during sandbox run" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
