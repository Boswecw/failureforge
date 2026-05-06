"""HTTP clients for the Slice 06 operator approval + SMITH handshake routes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx


class PromotionPushOutcome(str, Enum):
    accepted = "accepted"
    accepted_idempotent = "accepted_idempotent"
    rejected = "rejected"
    transport_failure = "transport_failure"


@dataclass
class PromotionPushResult:
    outcome: PromotionPushOutcome
    record_type: str
    record_id: str | None = None
    error_class: str | None = None
    error_message: str | None = None
    raw: dict[str, Any] | None = None


class _BaseClient:
    """Common HTTP plumbing shared by the operator and SMITH clients."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8005",
        identity: str,
        token: str,
        timeout_s: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        # Identity headers are sent per-request, not stamped on the shared
        # client, so multiple clients sharing one TestClient don't clobber
        # each other's identity.
        self._identity = identity
        self._token = token
        self._owns_client = http_client is None
        if http_client is not None:
            self._client = http_client
        else:
            self._client = httpx.Client(
                base_url=base_url.rstrip("/"),
                timeout=timeout_s,
                headers={"Content-Type": "application/json"},
            )

    def _identity_headers(self) -> dict[str, str]:
        return {
            "X-FailureForge-Writer": self._identity,
            "X-FailureForge-Token": self._token,
            "Content-Type": "application/json",
        }

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _post(
        self,
        *,
        path: str,
        payload: dict[str, Any],
        record_type: str,
        record_id: str | None,
    ) -> PromotionPushResult:
        try:
            resp = self._client.post(path, json=payload, headers=self._identity_headers())
        except httpx.HTTPError as exc:
            return PromotionPushResult(
                outcome=PromotionPushOutcome.transport_failure,
                record_type=record_type,
                record_id=record_id,
                error_class="transport_failure",
                error_message=str(exc),
            )
        try:
            body = resp.json()
        except Exception:
            body = {}
        if resp.status_code == 200:
            return PromotionPushResult(
                outcome=PromotionPushOutcome.accepted,
                record_type=record_type,
                record_id=record_id,
                raw=body if isinstance(body, dict) else None,
            )
        err_body: dict[str, Any] = {}
        if isinstance(body, dict):
            err_body = body.get("detail", body) if isinstance(body.get("detail"), dict) else body
        return PromotionPushResult(
            outcome=PromotionPushOutcome.rejected,
            record_type=record_type,
            record_id=record_id,
            error_class=err_body.get("error_class") or f"http_{resp.status_code}",
            error_message=err_body.get("message") or f"http {resp.status_code}",
            raw=body if isinstance(body, dict) else None,
        )


class OperatorPromotionClient(_BaseClient):
    """Submits operator approvals and promotion candidates."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8005",
        token: str = "local-operator",
        timeout_s: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            identity="operator",
            token=token,
            timeout_s=timeout_s,
            http_client=http_client,
        )

    def submit_approval(self, approval: dict[str, Any]) -> PromotionPushResult:
        return self._post(
            path="/api/v1/failureforge/approvals",
            payload=approval,
            record_type="approval_receipt",
            record_id=approval.get("approval_receipt_id"),
        )

    def submit_candidate(self, candidate: dict[str, Any]) -> PromotionPushResult:
        return self._post(
            path="/api/v1/failureforge/promotion-candidates",
            payload=candidate,
            record_type="promotion_candidate",
            record_id=candidate.get("promotion_candidate_id"),
        )

    def withdraw_candidate(
        self, candidate_id: str, *, reason: str
    ) -> PromotionPushResult:
        return self._post(
            path=f"/api/v1/failureforge/promotion-candidates/{candidate_id}/withdraw",
            payload={"reason": reason},
            record_type="promotion_candidate",
            record_id=candidate_id,
        )


class SmithHandshakeClient(_BaseClient):
    """SMITH-side client. In production SMITH would own this credential."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8005",
        token: str = "local-smith",
        timeout_s: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            identity="smith",
            token=token,
            timeout_s=timeout_s,
            http_client=http_client,
        )

    def pickup(self, candidate_id: str) -> PromotionPushResult:
        return self._post(
            path=f"/api/v1/failureforge/promotion-candidates/{candidate_id}/smith-pickup",
            payload={},
            record_type="promotion_candidate",
            record_id=candidate_id,
        )

    def decide(
        self, candidate_id: str, *, outcome: str, reason: str | None = None
    ) -> PromotionPushResult:
        body: dict[str, Any] = {"outcome": outcome}
        if reason is not None:
            body["reason"] = reason
        return self._post(
            path=f"/api/v1/failureforge/promotion-candidates/{candidate_id}/smith-decision",
            payload=body,
            record_type="promotion_candidate",
            record_id=candidate_id,
        )
