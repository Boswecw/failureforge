"""Slice 06 — operator + SMITH client round trips against an in-process app."""

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

from failureforge.persistence import DataForgeFailureForgeClient  # noqa: E402
from failureforge.promotion import (  # noqa: E402
    OperatorPromotionClient,
    PromotionPushOutcome,
    SmithHandshakeClient,
    build_approval_receipt,
    build_promotion_candidate,
)
from failureforge.runtime.sandbox import SandboxRunner  # noqa: E402

_FF_ROOT = Path(__file__).resolve().parents[1]


def _make_app() -> FastAPI:
    from app.failureforge.promotion import PromotionService
    from app.failureforge.router import router as failureforge_router
    from app.failureforge.service import FailureForgeService

    fa = FastAPI()
    fa.include_router(failureforge_router)
    svc = FailureForgeService()
    fa.state.failureforge_service = svc
    fa.state.failureforge_promotion_service = PromotionService(failureforge_service=svc)
    return fa


@pytest.fixture
def app() -> FastAPI:
    return _make_app()


@pytest.fixture
def http(app: FastAPI) -> TestClient:
    return TestClient(app)


def _seed_run(http: TestClient, tmp_path: Path) -> dict:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_FF_ROOT / "sandbox-targets" / "example-repo",
    )
    runner.run(sandbox_run_id="SR-promo-e2e")
    from failureforge.reporting.scorer import (
        build_hardening_report,
        load_and_verify_receipts,
        write_hardening_artifacts,
    )

    receipts = load_and_verify_receipts(sandbox / "receipts")
    report = build_hardening_report(
        sandbox_run_id="SR-promo-e2e", target_repo="example-repo", receipts=receipts
    )
    write_hardening_artifacts(report=report, sandbox_root=sandbox)

    push = DataForgeFailureForgeClient(http_client=http)
    summary = push.push_run_bundle_from_disk(
        run_id="SR-promo-e2e", sandbox_root=sandbox
    )
    assert summary.all_accepted
    return {"sandbox": sandbox}


def test_full_operator_smith_round_trip(tmp_path: Path, http: TestClient, app: FastAPI):
    _seed_run(http, tmp_path)
    receipts = http.get(
        "/api/v1/failureforge/receipts",
        params={"sandbox_run_id": "SR-promo-e2e", "classification": "duplicate_replay"},
    ).json()["receipts"]
    assert receipts
    receipt_id = receipts[0]["receipt_id"]

    operator = OperatorPromotionClient(http_client=http)
    smith = SmithHandshakeClient(http_client=http)

    approval = build_approval_receipt(
        failure_receipt_id=receipt_id,
        decided_by="operator:demo",
        decision="approved_for_smith_review",
        prior_promotion_status="pending_operator_review",
    )
    a_res = operator.submit_approval(approval)
    assert a_res.outcome == PromotionPushOutcome.accepted

    candidate = build_promotion_candidate(
        failure_receipt_id=receipt_id,
        approval_receipt_id=approval["approval_receipt_id"],
        target_repo="example-repo",
        candidate_kind="regression_test",
        candidate_payload={
            "title": "regression test for duplicate_replay",
            "test_steps": ["upsert(K1,V1)", "upsert(K1,V1)", "assert size==1"],
        },
    )
    c_res = operator.submit_candidate(candidate)
    assert c_res.outcome == PromotionPushOutcome.accepted

    pickup = smith.pickup(candidate["promotion_candidate_id"])
    assert pickup.outcome == PromotionPushOutcome.accepted

    decide = smith.decide(
        candidate["promotion_candidate_id"], outcome="accepted_by_smith"
    )
    assert decide.outcome == PromotionPushOutcome.accepted

    final = http.get(
        f"/api/v1/failureforge/promotion-candidates/{candidate['promotion_candidate_id']}"
    ).json()
    assert final["smith_handoff_status"] == "accepted_by_smith"


def test_failureforge_cannot_call_promotion_endpoints(tmp_path: Path, http: TestClient):
    _seed_run(http, tmp_path)
    receipts = http.get(
        "/api/v1/failureforge/receipts",
        params={"sandbox_run_id": "SR-promo-e2e", "classification": "duplicate_replay"},
    ).json()["receipts"]
    receipt_id = receipts[0]["receipt_id"]
    approval = build_approval_receipt(
        failure_receipt_id=receipt_id,
        decided_by="impostor",
        decision="approved_for_smith_review",
        prior_promotion_status="pending_operator_review",
    )
    rouge = OperatorPromotionClient(http_client=http, token="bad")
    res = rouge.submit_approval(approval)
    assert res.outcome == PromotionPushOutcome.rejected
    assert res.error_class in ("forbidden", "unknown_writer")


def test_operator_withdraw_then_smith_pickup_blocked(tmp_path: Path, http: TestClient):
    _seed_run(http, tmp_path)
    receipts = http.get(
        "/api/v1/failureforge/receipts",
        params={"sandbox_run_id": "SR-promo-e2e", "classification": "duplicate_replay"},
    ).json()["receipts"]
    receipt_id = receipts[0]["receipt_id"]

    operator = OperatorPromotionClient(http_client=http)
    smith = SmithHandshakeClient(http_client=http)

    approval = build_approval_receipt(
        failure_receipt_id=receipt_id,
        decided_by="operator:demo",
        decision="approved_for_smith_review",
        prior_promotion_status="pending_operator_review",
    )
    operator.submit_approval(approval)
    candidate = build_promotion_candidate(
        failure_receipt_id=receipt_id,
        approval_receipt_id=approval["approval_receipt_id"],
        target_repo="example-repo",
        candidate_kind="regression_test",
        candidate_payload={"steps": []},
    )
    operator.submit_candidate(candidate)

    withdraw = operator.withdraw_candidate(
        candidate["promotion_candidate_id"], reason="rolled back by operator"
    )
    assert withdraw.outcome == PromotionPushOutcome.accepted

    pickup = smith.pickup(candidate["promotion_candidate_id"])
    assert pickup.outcome == PromotionPushOutcome.rejected
    assert pickup.error_class == "invalid_transition"
