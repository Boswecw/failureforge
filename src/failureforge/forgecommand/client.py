"""Operator read-only client for FailureForge (Slice 05).

Targets the ``/api/v1/failureforge/operator/...`` routes on DataForge Local.
Renders compact terminal views suitable for ForgeCommand's morning briefing
or for direct operator inspection from the CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class OperatorClient:
    """Wraps an httpx.Client so tests can inject a TestClient and production
    can pass a real Client against http://127.0.0.1:8005."""

    http: httpx.Client

    def list_runs(
        self,
        *,
        target_repo: str | None = None,
        status: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if target_repo:
            params["target_repo"] = target_repo
        if status:
            params["status"] = status
        r = self.http.get("/api/v1/failureforge/operator/runs", params=params)
        r.raise_for_status()
        return r.json()["runs"]

    def get_run_detail(self, run_id: str) -> dict[str, Any]:
        r = self.http.get(f"/api/v1/failureforge/operator/runs/{run_id}")
        r.raise_for_status()
        return r.json()

    def get_receipt_detail(self, receipt_id: str) -> dict[str, Any]:
        r = self.http.get(f"/api/v1/failureforge/operator/receipts/{receipt_id}")
        r.raise_for_status()
        return r.json()

    def morning_report(
        self,
        *,
        target_repo: str | None = None,
        runs_limit: int = 10,
        top_findings_limit: int = 10,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "runs_limit": runs_limit,
            "top_findings_limit": top_findings_limit,
        }
        if target_repo:
            params["target_repo"] = target_repo
        r = self.http.get("/api/v1/failureforge/operator/morning-report", params=params)
        r.raise_for_status()
        return r.json()


# ---- terminal renderers ---------------------------------------------------


def render_morning_report_text(view: dict[str, Any]) -> str:
    lines: list[str] = ["FailureForge — Morning Report", ""]
    summary = view.get("summary", {})
    target = view.get("target_repo") or "(all targets)"
    lines.append(f"Target:                {target}")
    lines.append(f"Runs:                  {summary.get('runs_total', 0)}")
    lines.append(f"Receipts:              {summary.get('receipts_total', 0)}")
    lines.append(f"Reproducible:          {summary.get('reproducible_total', 0)}")
    lines.append(f"Ready for gate:        {summary.get('ready_for_gate_total', 0)}")
    if summary.get("top_severity"):
        lines.append(f"Top severity:          {summary['top_severity']}")
        lines.append(f"Top recommended fix:   {summary.get('top_recommended_fix', '')}")
    lines.append("")
    lines.append("Recent runs:")
    if not view.get("runs"):
        lines.append("  (none)")
    for run in view.get("runs", []):
        flag = "✓" if run["has_report"] else "·"
        lines.append(
            f"  {flag} {run['sandbox_run_id']}  target={run['target_repo']}  "
            f"status={run['status']}  receipts={run['receipt_count']}  "
            f"reproducible={run['reproducible_count']}"
        )
    lines.append("")
    lines.append("Top findings ready for gate:")
    if not view.get("top_findings"):
        lines.append("  (none)")
    for f in view.get("top_findings", []):
        lines.append(
            f"  [{f['severity'].upper()}] {f['classification']} "
            f"(score={f['score']}, run={f['sandbox_run_id']}, target={f['target_repo']})"
        )
        lines.append(f"      Recommended fix: {f['recommended_fix']}")
        lines.append(f"      Replay:          {f['repro_command']}")
        lines.append(f"      Receipts:        {', '.join(f['receipts'])}")
    return "\n".join(lines).rstrip() + "\n"


def render_run_detail_text(detail: dict[str, Any]) -> str:
    summary = detail["summary"]
    lines = [
        f"Sandbox run {summary['sandbox_run_id']} — {summary['target_repo']}",
        "",
        f"Status:           {summary['status']}",
        f"Started at:       {summary['started_at']}",
        f"Completed at:     {summary.get('completed_at') or '(running)'}",
        f"Receipts:         {summary['receipt_count']}",
        f"Reproducible:     {summary['reproducible_count']}",
        f"Has report:       {'yes' if summary['has_report'] else 'no'}",
        "",
    ]
    if detail.get("report"):
        report = detail["report"]
        lines.append("Hardening report ranked findings:")
        for f in report.get("ranked_findings", []):
            lines.append(
                f"  {f['rank']}. [{f['severity'].upper()}] {f['classification']} "
                f"(score={f['score']}, freq={f['frequency']}, ready_for_gate={f['ready_for_gate']})"
            )
            lines.append(f"     Recommended fix: {f['recommended_fix']}")
            lines.append(f"     Replay:          {f['repro_command']}")
        lines.append("")
    lines.append("Receipts:")
    for r in detail.get("receipts", []):
        lines.append(
            f"  {r['receipt_id']}  [{r['severity'].upper()}] {r['classification']}  "
            f"reproducible={r['reproducible']}  promotion={r['promotion_status']}"
        )
        lines.append(f"     Replay: {r['repro_command']}")
    return "\n".join(lines).rstrip() + "\n"


def render_receipt_detail_text(receipt: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Receipt {receipt['receipt_id']}",
            "",
            f"Sandbox run:        {receipt['sandbox_run_id']}",
            f"Failure case:       {receipt['failure_case_id']}",
            f"Target repo:        {receipt['target_repo']}",
            f"Classification:     {receipt['classification']}",
            f"Severity:           {receipt['severity']}",
            f"Reproducible:       {receipt['reproducible']}",
            f"Promotion status:   {receipt['promotion_status']}",
            f"Created at:         {receipt['created_at']}",
            f"Receipt hash:       {receipt['receipt_hash']}",
            "",
            "Expected result:",
            f"  {receipt['expected_result']}",
            "",
            "Actual result:",
            f"  {receipt['actual_result']}",
            "",
            "Replay command (copy/paste):",
            f"  {receipt['repro_command']}",
            "",
        ]
    )
