"""Slice 01 acceptance tests.

Plan §10:

1. Contracts validate sample JSON.
2. Sandbox workspace is copied, not original repo.
3. Edge-case agent produces a FailureCase.v1.
4. Failure execution produces a FailureHarvestReceipt.v1.
5. Receipt includes expected_result and actual_result.
6. Receipt includes reproducible boolean.
7. Receipt includes replay command.
8. HardeningReport.v1 includes at least one ranked finding.
9. No canonical repo files are modified.
10. All artifacts are written under sandbox/reports or sandbox/receipts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from failureforge.reporting.scorer import (
    build_hardening_report,
    load_and_verify_receipts,
    write_hardening_artifacts,
)
from failureforge.runtime.replay import replay_receipt
from failureforge.runtime.sandbox import SandboxRunner
from failureforge.validation import (
    validate_failure_case,
    validate_failure_receipt,
    validate_hardening_report,
    validate_sandbox_run,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _hash_tree(p: Path) -> str:
    sha = hashlib.sha256()
    for child in sorted(p.rglob("*")):
        if child.is_file():
            sha.update(child.relative_to(p).as_posix().encode("utf-8"))
            sha.update(child.read_bytes())
    return sha.hexdigest()


@pytest.fixture
def fresh_sandbox(tmp_path: Path) -> Path:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    return sandbox


# 1. ---------------------------------------------------------------- contracts


def test_contracts_validate_sample_json():
    sample_case = {
        "schema_version": "FailureCase.v1",
        "failure_case_id": "FC-0001",
        "target_repo": "example-repo",
        "target_area": "registry_scan",
        "invariant": "Duplicate input must not create duplicate canonical records.",
        "attack_type": "duplicate_replay",
        "attack_description": "Replay same request under retry.",
        "expected_result": "Existing result reused.",
        "agent_lane": "edge_case",
        "created_at": "2026-05-04T00:00:00Z",
    }
    validate_failure_case(sample_case)

    sample_run = {
        "schema_version": "SandboxRun.v1",
        "sandbox_run_id": "SR-0001",
        "target_repo": "example-repo",
        "source_ref": "master",
        "workspace_path": "sandbox/workspaces/SR-0001/example-repo",
        "agent_lanes": ["edge_case"],
        "started_at": "2026-05-04T00:00:00Z",
        "status": "running",
    }
    validate_sandbox_run(sample_run)

    from failureforge.validation import apply_receipt_hash

    sample_receipt = apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": "FHR-0001",
            "failure_case_id": "FC-0001",
            "sandbox_run_id": "SR-0001",
            "target_repo": "example-repo",
            "target_ref": "master",
            "classification": "duplicate_replay",
            "severity": "high",
            "expected_result": "Existing result reused.",
            "actual_result": "Duplicate created.",
            "reproducible": True,
            "repro_command": "./scripts/replay_failure.sh sandbox/receipts/FHR-0001.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-04T00:00:00Z",
        }
    )
    validate_failure_receipt(sample_receipt)

    sample_report = {
        "schema_version": "HardeningReport.v1",
        "report_id": "HR-0001",
        "sandbox_run_id": "SR-0001",
        "target_repo": "example-repo",
        "summary": "1 high severity finding.",
        "ranked_findings": [],
        "created_at": "2026-05-04T00:00:00Z",
    }
    validate_hardening_report(sample_report)


# 2 + 9. ---------------------------------------------------- workspace isolation


def test_sandbox_workspace_is_a_copy_and_canonical_target_is_unchanged(fresh_sandbox: Path):
    target_source = _REPO_ROOT / "sandbox-targets" / "example-repo"
    canonical_hash_before = _hash_tree(target_source)

    runner = SandboxRunner(
        sandbox_root=fresh_sandbox,
        target_repo_name="example-repo",
        target_repo_source=target_source,
    )
    result = runner.run(sandbox_run_id="SR-isolation")

    assert (fresh_sandbox / "workspaces" / "SR-isolation" / "example-repo").exists()
    # Canonical target must not have changed.
    assert _hash_tree(target_source) == canonical_hash_before
    # All run artifacts live under the sandbox.
    for p in result["receipt_paths"]:
        assert Path(p).is_relative_to(fresh_sandbox)


def test_runner_refuses_canonical_target_inside_sandbox_tree(fresh_sandbox: Path):
    bad_target = fresh_sandbox / "fake-target"
    bad_target.mkdir(parents=True)
    (bad_target / "registry.py").write_text("class Registry: pass\n", encoding="utf-8")
    with pytest.raises(ValueError):
        SandboxRunner(
            sandbox_root=fresh_sandbox,
            target_repo_name="fake-target",
            target_repo_source=bad_target,
        )


# 3 + 4 + 5 + 6 + 7. ---------------------------------------------- receipts


def test_edge_case_agent_emits_failure_cases_and_receipts(fresh_sandbox: Path):
    runner = SandboxRunner(
        sandbox_root=fresh_sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    result = runner.run(sandbox_run_id="SR-receipts")
    assert len(result["receipt_paths"]) >= 1

    # A receipt for the duplicate_replay invariant must exist with reproducible=True
    # and an actual_result that diverges from expected_result.
    receipts = [json.loads(Path(p).read_text()) for p in result["receipt_paths"]]
    dup = next((r for r in receipts if r["classification"] == "duplicate_replay"), None)
    assert dup is not None
    assert dup["expected_result"] != dup["actual_result"]
    assert dup["reproducible"] is True
    assert dup["repro_command"].startswith("./scripts/replay_failure.sh ")
    # Hash field must commit to the rest of the document.
    from failureforge.validation import verify_receipt_hash

    verify_receipt_hash(dup)


# 8 + 10. ----------------------------------------------- hardening report shape


def test_hardening_report_has_at_least_one_ranked_finding(fresh_sandbox: Path):
    runner = SandboxRunner(
        sandbox_root=fresh_sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    runner.run(sandbox_run_id="SR-report")
    receipts = load_and_verify_receipts(fresh_sandbox / "receipts")
    report = build_hardening_report(
        sandbox_run_id="SR-report",
        target_repo="example-repo",
        receipts=receipts,
    )
    assert len(report["ranked_findings"]) >= 1
    json_path, md_path = write_hardening_artifacts(report=report, sandbox_root=fresh_sandbox)
    assert json_path.is_relative_to(fresh_sandbox / "reports")
    assert md_path.is_relative_to(fresh_sandbox / "reports")
    md = md_path.read_text()
    assert "Hardening Report" in md
    assert "Ranked Findings" in md


# replay determinism --------------------------------------------------------


def test_replay_recreates_the_original_outcome(fresh_sandbox: Path):
    target_source = _REPO_ROOT / "sandbox-targets" / "example-repo"
    runner = SandboxRunner(
        sandbox_root=fresh_sandbox,
        target_repo_name="example-repo",
        target_repo_source=target_source,
    )
    result = runner.run(sandbox_run_id="SR-replay")
    dup_receipt_path = next(
        Path(p)
        for p in result["receipt_paths"]
        if "duplicate_replay" in json.loads(Path(p).read_text())["classification"]
    )
    replay = replay_receipt(
        receipt_path=dup_receipt_path,
        sandbox_root=fresh_sandbox,
        target_repo_source=target_source,
    )
    assert replay.matches_original is True
    assert replay.replayed_classification == "duplicate_replay"
