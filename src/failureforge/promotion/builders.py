"""Builders for ApprovalReceipt.v1 and PromotionCandidate.v1 records."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from failureforge.validation import (
    apply_approval_hash,
    apply_candidate_hash,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


_DECISION_TO_NEW_STATUS: dict[str, str] = {
    "approved_for_test_generation": "approved_for_test_generation",
    "approved_for_patch_advice": "approved_for_patch_advice",
    "approved_for_smith_review": "approved_for_smith_review",
    "rejected_by_operator": "rejected_by_operator",
    "superseded": "superseded",
}


def build_approval_receipt(
    *,
    failure_receipt_id: str,
    decided_by: str,
    decision: str,
    prior_promotion_status: str,
    reason: str | None = None,
    decided_at: str | None = None,
    approval_receipt_id: str | None = None,
) -> dict[str, Any]:
    if decision not in _DECISION_TO_NEW_STATUS:
        raise ValueError(f"unknown decision: {decision}")
    decided_at = decided_at or _utc_now()
    new_status = _DECISION_TO_NEW_STATUS[decision]
    body: dict[str, Any] = {
        "schema_version": "ApprovalReceipt.v1",
        "approval_receipt_id": approval_receipt_id
        or _stable_id("AR", failure_receipt_id, decision, decided_at),
        "failure_receipt_id": failure_receipt_id,
        "decided_by": decided_by,
        "decided_at": decided_at,
        "decision": decision,
        "prior_promotion_status": prior_promotion_status,
        "new_promotion_status": new_status,
    }
    if reason is not None:
        body["reason"] = reason
    return apply_approval_hash(body)


def build_promotion_candidate(
    *,
    failure_receipt_id: str,
    approval_receipt_id: str,
    target_repo: str,
    candidate_kind: str,
    candidate_payload: dict[str, Any],
    promotion_candidate_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    created_at = created_at or _utc_now()
    body: dict[str, Any] = {
        "schema_version": "PromotionCandidate.v1",
        "promotion_candidate_id": promotion_candidate_id
        or _stable_id(
            "PC", failure_receipt_id, approval_receipt_id, candidate_kind, created_at
        ),
        "failure_receipt_id": failure_receipt_id,
        "approval_receipt_id": approval_receipt_id,
        "target_repo": target_repo,
        "candidate_kind": candidate_kind,
        "candidate_payload": candidate_payload,
        "smith_handoff_status": "pending_smith_pickup",
        "created_at": created_at,
    }
    return apply_candidate_hash(body)
