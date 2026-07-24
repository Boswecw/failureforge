"""Receipt hash construction and immutability verification (Slice 02)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class ReceiptHashMismatch(Exception):
    """Raised when a receipt's stored hash does not match its computed hash."""


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def compute_receipt_hash(receipt: dict[str, Any]) -> str:
    """Compute the immutable hash for a FailureHarvestReceipt.

    The hash commits to every field except ``receipt_hash`` itself. Re-emitting
    the same receipt JSON produces the same hash — modifying any field after
    the hash is applied invalidates it.
    """
    payload = {k: v for k, v in receipt.items() if k != "receipt_hash"}
    return hashlib.sha256(_canonical(payload)).hexdigest()


def apply_receipt_hash(receipt: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``receipt`` with ``receipt_hash`` set to its canonical hash."""
    body = dict(receipt)
    body["receipt_hash"] = compute_receipt_hash(body)
    return body


def verify_receipt_hash(receipt: dict[str, Any]) -> None:
    """Raise ReceiptHashMismatch if the stored hash does not match the contents."""
    stored = receipt.get("receipt_hash")
    if not stored:
        raise ReceiptHashMismatch("receipt has no receipt_hash field")
    expected = compute_receipt_hash(receipt)
    if stored != expected:
        raise ReceiptHashMismatch(
            f"receipt_hash mismatch: stored={stored} computed={expected}"
        )


# ---- ApprovalReceipt --------------------------------------------------


class ApprovalHashMismatch(Exception):
    """Raised when an approval's stored hash does not match its computed hash."""


def compute_approval_hash(approval: dict[str, Any]) -> str:
    payload = {k: v for k, v in approval.items() if k != "approval_hash"}
    return hashlib.sha256(_canonical(payload)).hexdigest()


def apply_approval_hash(approval: dict[str, Any]) -> dict[str, Any]:
    body = dict(approval)
    body["approval_hash"] = compute_approval_hash(body)
    return body


def verify_approval_hash(approval: dict[str, Any]) -> None:
    stored = approval.get("approval_hash")
    if not stored:
        raise ApprovalHashMismatch("approval has no approval_hash field")
    expected = compute_approval_hash(approval)
    if stored != expected:
        raise ApprovalHashMismatch(
            f"approval_hash mismatch: stored={stored} computed={expected}"
        )


# ---- PromotionCandidate -----------------------------------------------


class CandidateHashMismatch(Exception):
    """Raised when a promotion candidate's stored hash does not match."""


# Fields covered by candidate_hash. SMITH-side decision fields and
# operator-withdrawal fields are intentionally NOT covered so SMITH can
# update them without invalidating the candidate's identity.
_CANDIDATE_STABLE_FIELDS = frozenset(
    {
        "schema_version",
        "promotion_candidate_id",
        "failure_receipt_id",
        "approval_receipt_id",
        "target_repo",
        "candidate_kind",
        "candidate_payload",
        "created_at",
    }
)


def compute_candidate_hash(candidate: dict[str, Any]) -> str:
    payload = {k: v for k, v in candidate.items() if k in _CANDIDATE_STABLE_FIELDS}
    return hashlib.sha256(_canonical(payload)).hexdigest()


def apply_candidate_hash(candidate: dict[str, Any]) -> dict[str, Any]:
    body = dict(candidate)
    body["candidate_hash"] = compute_candidate_hash(body)
    return body


def verify_candidate_hash(candidate: dict[str, Any]) -> None:
    stored = candidate.get("candidate_hash")
    if not stored:
        raise CandidateHashMismatch("candidate has no candidate_hash field")
    expected = compute_candidate_hash(candidate)
    if stored != expected:
        raise CandidateHashMismatch(
            f"candidate_hash mismatch: stored={stored} computed={expected}"
        )


# ---- ModelAdjudicationReceipt -----------------------------------------


class ModelAdjudicationHashMismatch(Exception):
    """Raised when a model adjudication receipt's stored hash does not match."""


def compute_model_adjudication_hash(receipt: dict[str, Any]) -> str:
    payload = {k: v for k, v in receipt.items() if k != "adjudication_hash"}
    return hashlib.sha256(_canonical(payload)).hexdigest()


def apply_model_adjudication_hash(receipt: dict[str, Any]) -> dict[str, Any]:
    body = dict(receipt)
    body["adjudication_hash"] = compute_model_adjudication_hash(body)
    return body


def verify_model_adjudication_hash(receipt: dict[str, Any]) -> None:
    stored = receipt.get("adjudication_hash")
    if not stored:
        raise ModelAdjudicationHashMismatch(
            "model adjudication receipt has no adjudication_hash field"
        )
    expected = compute_model_adjudication_hash(receipt)
    if stored != expected:
        raise ModelAdjudicationHashMismatch(
            f"adjudication_hash mismatch: stored={stored} computed={expected}"
        )
