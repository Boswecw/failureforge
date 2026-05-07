"""Slice 20 replay canonical-mutation guard tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from failureforge.runtime import CanonicalSourceMutationError
from failureforge.runtime.replay import replay_receipt
from failureforge.runtime.sandbox import AttackOutcome
from failureforge.validation import apply_receipt_hash


_ROOT = Path(__file__).resolve().parents[1]


def _seed_receipt(path: Path) -> None:
    receipt = apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-s20-replay",
            "failure_case_id": "FC-0001",
            "sandbox_run_id": "SR-s20-original",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": "high",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate created.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-s20-replay.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-07T00:00:00Z",
        }
    )
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def test_replay_fails_closed_when_canonical_source_hash_changes(
    monkeypatch, tmp_path: Path
):
    import failureforge.runtime.replay as replay_module

    source = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", source)
    sandbox = tmp_path / "sandbox"
    receipt_path = tmp_path / "receipt.json"
    _seed_receipt(receipt_path)

    def mutating_attack(*, workspace: Path, case):
        source.joinpath("MUTATED.txt").write_text("bad\n", encoding="utf-8")
        return AttackOutcome(
            failure_case=case,
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            expected_result=case.expected_result,
            actual_result="Duplicate created.",
            stdout_text="replayed\n",
            stderr_text="",
            exit_code=0,
        )

    monkeypatch.setattr(replay_module, "run_attack_against_target", mutating_attack)

    with pytest.raises(CanonicalSourceMutationError) as raised:
        replay_receipt(
            receipt_path=receipt_path,
            sandbox_root=sandbox,
            target_repo_source=source,
        )

    failed_run = raised.value.sandbox_run
    assert failed_run["sandbox_run_id"] == "SR-replay-FHR-s20-replay"
    assert failed_run["status"] == "failed"
    assert failed_run["receipt_count"] == 0
    assert failed_run["canonical_source_mutated"] is True
    assert failed_run["canonical_source_hash_before"] != failed_run[
        "canonical_source_hash_after"
    ]

    run_dir = sandbox / "runs" / "SR-replay-FHR-s20-replay"
    disk_run = json.loads((run_dir / "sandbox_run.json").read_text(encoding="utf-8"))
    assert disk_run == failed_run
    assert (run_dir / "exit_code.txt").read_text(encoding="utf-8") == "5\n"
    assert list((sandbox / "receipts").glob("FHR-*.json")) == []
