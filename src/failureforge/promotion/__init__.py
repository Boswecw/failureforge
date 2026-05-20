"""Operator-side helpers for FailureForge Slice 06.

Builds ApprovalReceipt and PromotionCandidate records and pushes them to
DataForge Local under the operator identity. Includes a small SMITH-side
client for tests / dev use; in production, SMITH carries its own credentials
and would not depend on this module.
"""

from failureforge.promotion.builders import (
    build_approval_receipt,
    build_promotion_candidate,
)
from failureforge.promotion.client import (
    OperatorPromotionClient,
    PromotionPushOutcome,
    PromotionPushResult,
    SmithHandshakeClient,
)

__all__ = [
    "build_approval_receipt",
    "build_promotion_candidate",
    "OperatorPromotionClient",
    "SmithHandshakeClient",
    "PromotionPushOutcome",
    "PromotionPushResult",
]
