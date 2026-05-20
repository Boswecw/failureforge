"""Slice 14 adapter-aware replay tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from failureforge.cli import main
from failureforge.runtime import SandboxRunner, TargetAdapterError, load_target_adapter
from failureforge.runtime.replay import replay_receipt
from failureforge.validation import apply_receipt_hash

_ROOT = Path(__file__).resolve().parents[1]


def _adapter() -> dict:
    return load_target_adapter(_ROOT / "fixtures/valid/TargetAdapter.v1.valid.json")


def _duplicate_receipt_path(paths: list[str]) -> Path:
    for raw_path in paths:
        path = Path(raw_path)
        body = json.loads(path.read_text(encoding="utf-8"))
        if body["classification"] == "duplicate_replay":
            return path
    raise AssertionError("duplicate_replay receipt not found")


def _seed_receipt(path: Path) -> None:
    receipt = apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-s14-cli",
            "failure_case_id": "FC-0001",
            "sandbox_run_id": "SR-s14-cli",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": "high",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate created.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-s14-cli.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-07T00:00:00Z",
        }
    )
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def test_replay_receipt_accepts_adapter_backed_external_source(tmp_path: Path):
    external = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", external)
    sandbox = tmp_path / "sandbox"
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=external,
        target_adapter=_adapter(),
    )
    result = runner.run(sandbox_run_id="SR-s14-external")
    receipt_path = _duplicate_receipt_path(result["receipt_paths"])

    replay = replay_receipt(
        receipt_path=receipt_path,
        sandbox_root=sandbox,
        target_repo_source=external,
        target_adapter=_adapter(),
    )

    assert replay.matches_original is True
    assert replay.replayed_classification == "duplicate_replay"


def test_replay_receipt_rejects_adapter_forbidden_source_path(tmp_path: Path):
    external = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", external)
    sandbox = tmp_path / "sandbox"
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=external,
        target_adapter=_adapter(),
    )
    result = runner.run(sandbox_run_id="SR-s14-forbidden")
    receipt_path = _duplicate_receipt_path(result["receipt_paths"])
    external.joinpath(".env").write_text("SECRET=do-not-copy\n", encoding="utf-8")

    with pytest.raises(TargetAdapterError, match="forbidden path exists"):
        replay_receipt(
            receipt_path=receipt_path,
            sandbox_root=sandbox,
            target_repo_source=external,
            target_adapter=_adapter(),
        )


def test_cli_replay_rejects_external_target_source_without_adapter(
    tmp_path: Path, capsys
):
    external = tmp_path / "example-repo"
    external.mkdir()
    receipt_path = tmp_path / "receipt.json"
    _seed_receipt(receipt_path)

    rc = main(["replay", str(receipt_path), "--target-source", str(external)])

    captured = capsys.readouterr()
    assert rc == 2
    assert "--target-source requires --adapter" in captured.err
