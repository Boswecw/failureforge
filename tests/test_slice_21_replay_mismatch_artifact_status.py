"""Slice 21 replay mismatch artifact status tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from failureforge.runtime.replay import replay_receipt
from failureforge.runtime.sandbox import AttackOutcome
from failureforge.validation import apply_receipt_hash

_ROOT = Path(__file__).resolve().parents[1]


def _seed_receipt(path: Path) -> None:
    receipt = apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-s21-replay",
            "failure_case_id": "FC-0001",
            "sandbox_run_id": "SR-s21-original",
            "target_repo": "example-repo",
            "target_ref": "local",
            "classification": "duplicate_replay",
            "severity": "high",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate created.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-s21-replay.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-07T00:00:00Z",
        }
    )
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def test_replay_mismatch_writes_failed_run_artifact(monkeypatch, tmp_path: Path):
    import failureforge.runtime.replay as replay_module

    source = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", source)
    sandbox = tmp_path / "sandbox"
    receipt_path = tmp_path / "receipt.json"
    _seed_receipt(receipt_path)

    def mismatching_attack(*, workspace: Path, case):
        return AttackOutcome(
            failure_case=case,
            classification="no_failure_observed",
            severity="info",
            reproducible=True,
            expected_result=case.expected_result,
            actual_result="Registry rejected duplicate as expected.",
            stdout_text="replayed with changed behavior\n",
            stderr_text="",
            exit_code=0,
        )

    monkeypatch.setattr(replay_module, "run_attack_against_target", mismatching_attack)

    result = replay_receipt(
        receipt_path=receipt_path,
        sandbox_root=sandbox,
        target_repo_source=source,
    )

    assert result.matches_original is False
    assert result.replayed_classification == "no_failure_observed"

    run_dir = sandbox / "runs" / "SR-replay-FHR-s21-replay"
    replay_run = json.loads((run_dir / "sandbox_run.json").read_text(encoding="utf-8"))
    assert replay_run["status"] == "failed"
    assert replay_run["receipt_count"] == 0
    assert replay_run["canonical_source_mutated"] is False
    assert (
        replay_run["canonical_source_hash_before"]
        == replay_run["canonical_source_hash_after"]
    )
    assert (run_dir / "exit_code.txt").read_text(encoding="utf-8") == "2\n"
    assert (run_dir / "stdout.log").read_text(
        encoding="utf-8"
    ) == "replayed with changed behavior\n"
