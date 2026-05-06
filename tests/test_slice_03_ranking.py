"""Slice 03 acceptance tests.

Plan §10 §"Slice 03 gates":

1. Critical reproducible failures rank above low non-reproducible failures.
2. Duplicate receipts can be grouped.
3. Report includes recommended fix field.
4. Report includes receipt IDs.
5. Report includes replay commands.
"""

from __future__ import annotations

from pathlib import Path

from failureforge.reporting.scorer import (
    build_hardening_report,
    render_hardening_markdown,
    score_findings,
)
from failureforge.validation import apply_receipt_hash


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _receipt(
    *,
    receipt_id: str,
    failure_case_id: str,
    classification: str,
    severity: str,
    reproducible: bool,
) -> dict:
    return apply_receipt_hash(
        {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": receipt_id,
            "failure_case_id": failure_case_id,
            "sandbox_run_id": "SR-rank",
            "target_repo": "example-repo",
            "target_ref": "master",
            "classification": classification,
            "severity": severity,
            "expected_result": "x",
            "actual_result": "y",
            "reproducible": reproducible,
            "repro_command": f"./scripts/replay_failure.sh sandbox/receipts/{receipt_id}.json",
            "artifact_paths": [],
            "promotion_status": "pending_operator_review",
            "created_at": "2026-05-04T00:00:00Z",
        }
    )


def test_critical_reproducible_outranks_low_non_reproducible():
    receipts = [
        _receipt(
            receipt_id="FHR-low-x",
            failure_case_id="FC-2001",
            classification="bad_unicode",
            severity="low",
            reproducible=False,
        ),
        _receipt(
            receipt_id="FHR-crit-x",
            failure_case_id="FC-1001",
            classification="state_failure",
            severity="critical",
            reproducible=True,
        ),
    ]
    findings = score_findings(receipts)
    assert findings[0]["failure_id"] == "FC-1001"
    assert findings[-1]["failure_id"] == "FC-2001"


def test_duplicate_receipts_are_grouped_into_one_finding():
    receipts = [
        _receipt(
            receipt_id="FHR-dup-1",
            failure_case_id="FC-1001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
        ),
        _receipt(
            receipt_id="FHR-dup-2",
            failure_case_id="FC-1001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
        ),
        _receipt(
            receipt_id="FHR-dup-3",
            failure_case_id="FC-1001",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
        ),
    ]
    findings = score_findings(receipts)
    assert len(findings) == 1
    f = findings[0]
    assert f["frequency"] == 3
    assert set(f["receipts"]) == {"FHR-dup-1", "FHR-dup-2", "FHR-dup-3"}


def test_report_includes_recommended_fix_receipt_ids_and_repro_commands():
    receipts = [
        _receipt(
            receipt_id="FHR-rep-1",
            failure_case_id="FC-rep-1",
            classification="duplicate_replay",
            severity="high",
            reproducible=True,
        )
    ]
    report = build_hardening_report(
        sandbox_run_id="SR-rep", target_repo="example-repo", receipts=receipts
    )
    f = report["ranked_findings"][0]
    assert f["recommended_fix"]
    assert "FHR-rep-1" in f["receipts"]
    assert f["repro_command"].endswith("FHR-rep-1.json")
    md = render_hardening_markdown(report)
    assert "Recommended fix" in md
    assert "FHR-rep-1" in md
    assert "replay_failure.sh" in md


def test_no_failure_observed_does_not_become_ready_for_gate():
    receipts = [
        _receipt(
            receipt_id="FHR-no-1",
            failure_case_id="FC-rep-2",
            classification="no_failure_observed",
            severity="info",
            reproducible=True,
        )
    ]
    findings = score_findings(receipts)
    assert findings[0]["ready_for_gate"] is False
