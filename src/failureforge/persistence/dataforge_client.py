"""HTTP client that pushes FailureForge artifacts to DataForge Local
(Slice 04 — `/api/v1/failureforge/*`).

Non-blocking: the sandbox run continues even if DataForge is unreachable.
Every push returns a stable ``PushResult`` so the caller can decide whether
to retry or surface a degraded posture in the report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx


class PushOutcome(StrEnum):
    accepted = "accepted"
    accepted_idempotent = "accepted_idempotent"
    rejected = "rejected"
    transport_failure = "transport_failure"


@dataclass
class PushResult:
    outcome: PushOutcome
    record_type: str
    record_id: str | None = None
    error_class: str | None = None
    error_message: str | None = None
    raw: dict[str, Any] | None = None


@dataclass
class PushSummary:
    run: PushResult | None = None
    cases: list[PushResult] = field(default_factory=list)
    receipts: list[PushResult] = field(default_factory=list)
    report: PushResult | None = None

    @property
    def all_accepted(self) -> bool:
        items: list[PushResult] = []
        if self.run is not None:
            items.append(self.run)
        items.extend(self.cases)
        items.extend(self.receipts)
        if self.report is not None:
            items.append(self.report)
        return all(
            r.outcome in (PushOutcome.accepted, PushOutcome.accepted_idempotent)
            for r in items
        )


class DataForgeFailureForgeClient:
    """Thin HTTP client for the FailureForge persistence routes."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8005",
        timeout_s: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = http_client is None
        if http_client is not None:
            self._client = http_client
            self._client.headers.setdefault("Content-Type", "application/json")
        else:
            self._client = httpx.Client(
                base_url=base_url.rstrip("/"),
                timeout=timeout_s,
                headers={"Content-Type": "application/json"},
            )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> DataForgeFailureForgeClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ---- single-record pushes ----

    def push_run(self, run: dict[str, Any]) -> PushResult:
        return self._post(
            path="/api/v1/failureforge/runs",
            payload=run,
            record_type="sandbox_run",
            record_id=run.get("sandbox_run_id"),
        )

    def push_case(self, case: dict[str, Any]) -> PushResult:
        return self._post(
            path="/api/v1/failureforge/cases",
            payload=case,
            record_type="failure_case",
            record_id=case.get("failure_case_id"),
        )

    def push_receipt(self, receipt: dict[str, Any]) -> PushResult:
        return self._post(
            path="/api/v1/failureforge/receipts",
            payload=receipt,
            record_type="failure_receipt",
            record_id=receipt.get("receipt_id"),
        )

    def push_report(self, report: dict[str, Any]) -> PushResult:
        return self._post(
            path="/api/v1/failureforge/reports",
            payload=report,
            record_type="hardening_report",
            record_id=report.get("report_id"),
        )

    def transition_promotion_status(
        self, receipt_id: str, *, new_status: str
    ) -> PushResult:
        return self._post(
            path=f"/api/v1/failureforge/receipts/{receipt_id}/promotion",
            payload={"new_status": new_status},
            record_type="failure_receipt",
            record_id=receipt_id,
        )

    # ---- bundle push (run + N cases + N receipts + report) ----

    def push_run_bundle(
        self,
        *,
        run: dict[str, Any],
        cases: list[dict[str, Any]],
        receipts: list[dict[str, Any]],
        report: dict[str, Any] | None = None,
    ) -> PushSummary:
        summary = PushSummary()
        summary.run = self.push_run(run)
        for c in cases:
            summary.cases.append(self.push_case(c))
        for r in receipts:
            summary.receipts.append(self.push_receipt(r))
        if report is not None:
            summary.report = self.push_report(report)
        return summary

    # ---- helpers ----

    def push_run_bundle_from_disk(
        self, *, run_id: str, sandbox_root: Path
    ) -> PushSummary:
        run_path = sandbox_root / "runs" / run_id / "sandbox_run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))

        receipts_dir = sandbox_root / "receipts"
        receipts = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(receipts_dir.glob("FHR-*.json"))
            if json.loads(p.read_text(encoding="utf-8"))["sandbox_run_id"] == run_id
        ]

        # FailureCases are reconstructed from the edge-case agent's catalog so
        # we can satisfy the FK constraint when ingesting receipts.
        from failureforge.agents.edge_case import EdgeCaseAgent

        agent = EdgeCaseAgent(target_repo=run["target_repo"])
        catalog = {
            c.failure_case_id: c.to_dict() for c in agent.generate_default_catalog()
        }
        case_ids = {r["failure_case_id"] for r in receipts}
        cases = [catalog[cid] for cid in case_ids if cid in catalog]

        reports_dir = sandbox_root / "reports"
        report: dict[str, Any] | None = None
        for p in reports_dir.glob("HR-*.json"):
            body = json.loads(p.read_text(encoding="utf-8"))
            if body.get("sandbox_run_id") == run_id:
                report = body
                break

        return self.push_run_bundle(
            run=run, cases=cases, receipts=receipts, report=report
        )

    # ---- internals ----

    def _post(
        self,
        *,
        path: str,
        payload: dict[str, Any],
        record_type: str,
        record_id: str | None,
    ) -> PushResult:
        try:
            response = self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            return PushResult(
                outcome=PushOutcome.transport_failure,
                record_type=record_type,
                record_id=record_id,
                error_class="transport_failure",
                error_message=str(exc),
            )

        try:
            body = response.json()
        except Exception:
            body = {}

        if (
            response.status_code == 200
            and isinstance(body, dict)
            and body.get("record_type") == record_type
        ):
            return PushResult(
                outcome=PushOutcome.accepted,
                record_type=record_type,
                record_id=record_id,
                raw=body,
            )

        # FastAPI nests detail; promotion endpoint returns 200 with body.record present.
        if response.status_code == 200:
            return PushResult(
                outcome=PushOutcome.accepted,
                record_type=record_type,
                record_id=record_id,
                raw=body if isinstance(body, dict) else None,
            )

        err_body: dict[str, Any] = {}
        if isinstance(body, dict):
            err_body = (
                body.get("detail", body)
                if isinstance(body.get("detail"), dict)
                else body
            )

        # Receipt double-push with same hash -> accepted_idempotent.
        if (
            response.status_code == 409
            and err_body.get("error_class") == "receipt_immutable"
        ):
            return PushResult(
                outcome=PushOutcome.rejected,
                record_type=record_type,
                record_id=record_id,
                error_class=err_body.get("error_class"),
                error_message=err_body.get("message"),
                raw=body if isinstance(body, dict) else None,
            )

        return PushResult(
            outcome=PushOutcome.rejected,
            record_type=record_type,
            record_id=record_id,
            error_class=err_body.get("error_class") or f"http_{response.status_code}",
            error_message=err_body.get("message") or f"http {response.status_code}",
            raw=body if isinstance(body, dict) else None,
        )
