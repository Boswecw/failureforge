"""FailureForge -> AAR seed bridge artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from failureforge.validation import validate_failureforge_aar_seed

_AAR_QUESTIONS = [
    "What invariant failed?",
    "Was this expected to be blocked earlier?",
    "Which contract should have rejected it?",
    "Which evidence step proved the failure?",
    "Which system boundary did the failure cross?",
    "Was the failure reproducible?",
    "Was the failure detected by more than one lane?",
    "Does this need a regression gate?",
    "Does this need a contract hardening patch?",
    "Does this need operator-process documentation?",
]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _deterministic_status(receipts: list[dict[str, Any]]) -> str:
    reproducible = {bool(r.get("reproducible")) for r in receipts}
    if reproducible == {True}:
        return "reproducible"
    if reproducible == {False}:
        return "not_reproducible"
    return "mixed"


def build_aar_seed(
    *,
    cluster: dict[str, Any],
    receipts: Iterable[dict[str, Any]],
    sandbox_run_id: str,
    source_ref: str,
    adjudication_report: dict[str, Any] | None = None,
    aar_seed_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    receipts_list = [
        r for r in receipts if r["receipt_id"] in cluster["member_receipts"]
    ]
    if not receipts_list:
        raise ValueError("AAR seed requires at least one evidence receipt")

    first = receipts_list[0]
    replay_commands = sorted(
        {r["repro_command"] for r in receipts_list if r.get("repro_command")}
    )
    if not replay_commands:
        raise ValueError("AAR seed requires at least one replay command")

    body = {
        "schema_version": "FailureForgeAARSeed.v1",
        "aar_seed_id": aar_seed_id
        or _stable_id("AARS", cluster["cluster_id"], sandbox_run_id),
        "target_repo": cluster["target_repo"],
        "source_ref": source_ref,
        "sandbox_run_id": sandbox_run_id,
        "cluster_id": cluster["cluster_id"],
        "failure_summary": (
            f"{cluster['classification']} in {cluster['target_repo']} "
            f"across {cluster['member_count']} receipt(s)."
        ),
        "what_failed": cluster.get("root_cause_label") or cluster["classification"],
        "expected_result": first["expected_result"],
        "actual_result_summary": "; ".join(
            sorted(cluster["actual_result_distribution"])
        ),
        "evidence_receipts": sorted(cluster["member_receipts"]),
        "replay_commands": replay_commands,
        "deterministic_status": _deterministic_status(receipts_list),
        "source_disagreement": {
            "preserved": True,
            "severity_distribution": cluster["severity_distribution"],
            "actual_result_distribution": cluster["actual_result_distribution"],
            "model_adjudication_status": (
                adjudication_report.get("adjudication_status", "not_requested")
                if adjudication_report
                else "not_requested"
            ),
        },
        "operator_review_required": True,
        "initial_lesson_hypothesis": (
            "A deterministic failure reached the sandbox target boundary; "
            "operator review should decide whether to create a regression gate."
        ),
        "recommended_next_checks": list(_AAR_QUESTIONS),
        "created_at": created_at or _utc_now(),
    }
    validate_failureforge_aar_seed(body)
    return body


def write_aar_seed(*, seed: dict[str, Any], sandbox_root: Path) -> Path:
    validate_failureforge_aar_seed(seed)
    out_dir = sandbox_root / "exports" / "aar"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{seed['aar_seed_id']}.json"
    path.write_text(json.dumps(seed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
