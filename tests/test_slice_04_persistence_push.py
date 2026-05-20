"""Slice 04 push-side tests.

Drive the FailureForge -> DataForge Local handshake against an in-process
FastAPI app. Uses the dataforge-Local FailureForgeService directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATAFORGE_LOCAL = _REPO_ROOT / "dataforge-Local"
if str(_DATAFORGE_LOCAL) not in sys.path:
    sys.path.insert(0, str(_DATAFORGE_LOCAL))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from failureforge.persistence import (  # noqa: E402
    DataForgeFailureForgeClient,
    PushOutcome,
)
from failureforge.runtime.sandbox import SandboxRunner  # noqa: E402

_FF_ROOT = Path(__file__).resolve().parents[1]


def _make_app() -> FastAPI:
    from app.failureforge.router import router as failureforge_router
    from app.failureforge.service import FailureForgeService

    fa = FastAPI()
    fa.include_router(failureforge_router)
    fa.state.failureforge_service = FailureForgeService()
    return fa


@pytest.fixture
def app() -> FastAPI:
    return _make_app()


@pytest.fixture
def client(app: FastAPI) -> DataForgeFailureForgeClient:
    return DataForgeFailureForgeClient(http_client=TestClient(app))


def test_full_run_bundle_push_round_trip(tmp_path: Path, client: DataForgeFailureForgeClient, app: FastAPI):
    """Run the sandbox into a tmp sandbox root, then push the whole bundle
    (run + cases + receipts + report) to DataForge Local in one call."""
    from failureforge.reporting.scorer import (
        build_hardening_report,
        load_and_verify_receipts,
        write_hardening_artifacts,
    )

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_FF_ROOT / "sandbox-targets" / "example-repo",
    )
    runner.run(sandbox_run_id="SR-push-001")
    receipts = load_and_verify_receipts(sandbox / "receipts")
    report = build_hardening_report(
        sandbox_run_id="SR-push-001",
        target_repo="example-repo",
        receipts=receipts,
    )
    write_hardening_artifacts(report=report, sandbox_root=sandbox)

    summary = client.push_run_bundle_from_disk(
        run_id="SR-push-001", sandbox_root=sandbox
    )
    assert summary.run is not None
    assert summary.run.outcome == PushOutcome.accepted
    assert all(r.outcome == PushOutcome.accepted for r in summary.cases)
    assert all(r.outcome == PushOutcome.accepted for r in summary.receipts)
    assert summary.report is not None
    assert summary.report.outcome == PushOutcome.accepted
    assert summary.all_accepted

    service = app.state.failureforge_service
    assert service.get_run("SR-push-001") is not None
    assert len(service.list_receipts(sandbox_run_id="SR-push-001")) == len(receipts)
    assert service.get_report_for_run("SR-push-001") is not None


def test_push_is_non_blocking_when_dataforge_unreachable(tmp_path: Path):
    """Sandbox must continue to write its on-disk artifacts even if the
    DataForge push fails. The client returns transport_failure, never raises."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_FF_ROOT / "sandbox-targets" / "example-repo",
    )
    runner.run(sandbox_run_id="SR-offline")

    bad = DataForgeFailureForgeClient(base_url="http://127.0.0.1:1", timeout_s=0.5)
    try:
        summary = bad.push_run_bundle_from_disk(
            run_id="SR-offline", sandbox_root=sandbox
        )
        assert summary.run is not None
        assert summary.run.outcome == PushOutcome.transport_failure
        assert not summary.all_accepted
        # Receipts on disk are still present and valid.
        from failureforge.reporting.scorer import load_and_verify_receipts

        load_and_verify_receipts(sandbox / "receipts")
    finally:
        bad.close()


def test_promotion_transition_via_client(tmp_path: Path, client: DataForgeFailureForgeClient, app: FastAPI):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_FF_ROOT / "sandbox-targets" / "example-repo",
    )
    runner.run(sandbox_run_id="SR-promo")
    client.push_run_bundle_from_disk(run_id="SR-promo", sandbox_root=sandbox)

    receipt_id = next(iter(app.state.failureforge_service.list_receipts(sandbox_run_id="SR-promo")))[
        "receipt_id"
    ]
    res = client.transition_promotion_status(receipt_id, new_status="approved_for_test_generation")
    assert res.outcome == PushOutcome.accepted
    rec = app.state.failureforge_service.get_receipt(receipt_id)
    assert rec["promotion_status"] == "approved_for_test_generation"
