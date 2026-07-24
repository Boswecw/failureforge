"""Slice 07 acceptance tests — multi-agent expansion + cross-agent agreement."""

from __future__ import annotations

import json
from pathlib import Path

from failureforge.agents import (
    ChaosAgent,
    ClassificationAgent,
    EdgeCaseAgent,
    MutationAgent,
    ReproductionAgent,
)
from failureforge.reporting.scorer import (
    build_hardening_report,
    load_and_verify_receipts,
    score_findings,
)
from failureforge.runtime.sandbox import SandboxRunner
from failureforge.validation import apply_receipt_hash

_REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------- ChaosAgent


def test_chaos_agent_emits_three_outcomes(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    chaos = ChaosAgent(target_repo="example-repo")
    result = runner.run(agents=[chaos], sandbox_run_id="SR-chaos")
    receipts = [json.loads(Path(p).read_text()) for p in result["receipt_paths"]]
    types = sorted(r["failure_case_id"] for r in receipts)
    assert "FC-CHAOS-CRASH" in types
    assert "FC-CHAOS-PARTIAL" in types
    assert "FC-CHAOS-TIMEOUT" in types
    assert all(r["agent_lane"] == "chaos" for r in receipts)


def test_chaos_partial_write_finds_state_failure(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    chaos = ChaosAgent(target_repo="example-repo")
    result = runner.run(agents=[chaos], sandbox_run_id="SR-chaos-partial")
    by_id = {
        json.loads(Path(p).read_text())["failure_case_id"]: json.loads(
            Path(p).read_text()
        )
        for p in result["receipt_paths"]
    }
    partial = by_id["FC-CHAOS-PARTIAL"]
    # The partial-write attack should detect that the registry retained a
    # record without `value` -> classification=state_failure, severity=high.
    assert partial["classification"] == "state_failure"
    assert partial["severity"] == "high"


# ---------------------------------------------------- MutationAgent


def test_mutation_agent_kills_path_check_and_reports_state_failure(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    mutation = MutationAgent(target_repo="example-repo")
    result = runner.run(agents=[mutation], sandbox_run_id="SR-mutation")
    by_id = {
        json.loads(Path(p).read_text())["failure_case_id"]: json.loads(
            Path(p).read_text()
        )
        for p in result["receipt_paths"]
    }
    path_mut = by_id["FC-MUTATION-PATH"]
    missing_mut = by_id["FC-MUTATION-MISSING"]
    # Deleting either guard should let the underlying attack slip through —
    # the mutation agent surfaces that as a state_failure / high severity.
    assert path_mut["classification"] == "state_failure"
    assert path_mut["severity"] == "high"
    assert "let the attack slip through" in path_mut["actual_result"]
    assert missing_mut["classification"] == "state_failure"


def test_mutation_agent_restores_workspace_after_run(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    mutation = MutationAgent(target_repo="example-repo")
    runner.run(agents=[mutation], sandbox_run_id="SR-mutation-restore")

    canonical = (
        _REPO_ROOT / "sandbox-targets" / "example-repo" / "registry.py"
    ).read_text()
    sandbox_copy = (
        sandbox / "workspaces" / "SR-mutation-restore" / "example-repo" / "registry.py"
    ).read_text()
    assert sandbox_copy == canonical


# ---------------------------------------------------- ReproductionAgent


def test_reproduction_agent_marks_deterministic_failures_reproducible(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    repro = ReproductionAgent(target_repo="example-repo", repeats=3)
    result = runner.run(agents=[repro], sandbox_run_id="SR-repro")
    receipts = [json.loads(Path(p).read_text()) for p in result["receipt_paths"]]
    by_id = {r["failure_case_id"]: r for r in receipts}

    dup = by_id["FC-REPRO-FC-0001"]
    assert dup["classification"] == "duplicate_replay"
    assert dup["reproducible"] is True
    assert "deterministic across" in dup["actual_result"]


# ---------------------------------------------------- ClassificationAgent


def test_classification_agent_escalates_duplicate_replay_to_critical(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    classifier = ClassificationAgent(target_repo="example-repo")
    result = runner.run(agents=[classifier], sandbox_run_id="SR-class")
    receipts = [json.loads(Path(p).read_text()) for p in result["receipt_paths"]]
    by_id = {r["failure_case_id"]: r for r in receipts}

    dup = by_id["FC-CLASS-FC-0001"]
    assert dup["classification"] == "duplicate_replay"
    assert dup["severity"] == "critical"
    assert "classifier_label=unbounded_growth" in dup["actual_result"]


# ---------------------------------------------------- cross-agent agreement


def _receipt(
    *,
    receipt_id: str,
    failure_case_id: str,
    classification: str,
    severity: str,
    reproducible: bool,
    agent_lane: str,
) -> dict:
    return apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": receipt_id,
            "failure_case_id": failure_case_id,
            "sandbox_run_id": "SR-agreement",
            "target_repo": "example-repo",
            "target_ref": "demo",
            "classification": classification,
            "severity": severity,
            "expected_result": "x",
            "actual_result": "y",
            "reproducible": reproducible,
            "repro_command": f"./scripts/replay_failure.sh sandbox/receipts/{receipt_id}.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-04T15:00:00Z",
            "agent_lane": agent_lane,
        }
    )


def test_cross_agent_agreement_boosts_score():
    edge = _receipt(
        receipt_id="FHR-agree-1",
        failure_case_id="FC-0001",
        classification="duplicate_replay",
        severity="high",
        reproducible=True,
        agent_lane="edge_case",
    )
    repro = _receipt(
        receipt_id="FHR-agree-2",
        failure_case_id="FC-REPRO-FC-0001",
        classification="duplicate_replay",
        severity="high",
        reproducible=True,
        agent_lane="reproduction",
    )
    classify = _receipt(
        receipt_id="FHR-agree-3",
        failure_case_id="FC-CLASS-FC-0001",
        classification="duplicate_replay",
        severity="critical",
        reproducible=True,
        agent_lane="classification",
    )

    findings = score_findings([edge, repro, classify])
    # All three lane-receipts cluster into a single finding by logical attack id.
    assert len(findings) == 1
    f = findings[0]
    assert f["lane_agreement"] == 3
    assert set(f["lanes"]) == {"edge_case", "reproduction", "classification"}
    # severity escalates to critical because classification agent says so.
    assert f["severity"] == "critical"

    # Compare to a single-lane baseline of equal severity — agreement boost
    # should be visible in the score.
    solo = _receipt(
        receipt_id="FHR-solo",
        failure_case_id="FC-0002",
        classification="bad_path",
        severity="critical",
        reproducible=True,
        agent_lane="edge_case",
    )
    solo_findings = score_findings([solo])
    assert findings[0]["score"] > solo_findings[0]["score"]


def test_hardening_report_records_lane_agreement():
    receipts = [
        _receipt(
            receipt_id="FHR-rep-1",
            failure_case_id="FC-0001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            agent_lane="edge_case",
        ),
        _receipt(
            receipt_id="FHR-rep-2",
            failure_case_id="FC-REPRO-FC-0001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
            agent_lane="reproduction",
        ),
    ]
    report = build_hardening_report(
        sandbox_run_id="SR-agreement",
        target_repo="example-repo",
        receipts=receipts,
    )
    assert report["ranked_findings"][0]["lane_agreement"] == 2
    assert set(report["ranked_findings"][0]["lanes"]) == {"edge_case", "reproduction"}


# ---------------------------------------------------- end-to-end multi-lane


def test_full_lane_set_runs_against_demo_target(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    agents = [
        EdgeCaseAgent(target_repo="example-repo"),
        ChaosAgent(target_repo="example-repo"),
        MutationAgent(target_repo="example-repo"),
        ReproductionAgent(target_repo="example-repo", repeats=2),
        ClassificationAgent(target_repo="example-repo"),
    ]
    result = runner.run(agents=agents, sandbox_run_id="SR-full-lanes")
    assert result["sandbox_run"]["agent_lanes"] == sorted(
        {"edge_case", "chaos", "mutation", "reproduction", "classification"}
    )

    receipts = load_and_verify_receipts(sandbox / "receipts")
    report = build_hardening_report(
        sandbox_run_id="SR-full-lanes", target_repo="example-repo", receipts=receipts
    )
    # The duplicate_replay finding should reflect agreement across at least
    # edge_case + reproduction + classification.
    dup_findings = [
        f
        for f in report["ranked_findings"]
        if f["classification"] == "duplicate_replay"
    ]
    assert dup_findings
    top_dup = max(dup_findings, key=lambda f: f["lane_agreement"])
    assert top_dup["lane_agreement"] >= 3
    assert "edge_case" in top_dup["lanes"]
    assert "reproduction" in top_dup["lanes"]
    assert "classification" in top_dup["lanes"]
    # And it should outrank lower-agreement findings of equal severity.
    assert top_dup["rank"] <= 2  # near the top


# ---------------------------------------------------- backwards compat


def test_legacy_single_agent_run_still_works(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_REPO_ROOT / "sandbox-targets" / "example-repo",
    )
    result = runner.run(sandbox_run_id="SR-legacy")
    assert result["sandbox_run"]["agent_lanes"] == ["edge_case"]
    assert len(result["receipt_paths"]) >= 1
