"""Deterministic replay for a FailureHarvestReceipt.

Reads the receipt, re-executes the original attack against the same copied
workspace (or re-copies it if missing), and verifies the actual_result still
matches. Returns a summary; does NOT mutate the receipt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from failureforge.agents.edge_case import FailureCaseSpec
from failureforge.runtime.sandbox import SandboxRunner, run_attack_against_target
from failureforge.validation import (
    verify_receipt_hash,
    validate_failure_receipt,
)


@dataclass
class ReplayResult:
    receipt_id: str
    matches_original: bool
    original_actual_result: str
    replayed_actual_result: str
    replayed_classification: str


def replay_receipt(
    *,
    receipt_path: Path,
    sandbox_root: Path,
    target_repo_source: Path,
    target_adapter: dict[str, Any] | None = None,
) -> ReplayResult:
    """Verify a receipt's hash, re-run the attack, and compare results.

    The workspace path inside the receipt is recreated by re-copying the
    target source. This keeps replay deterministic even if the workspace was
    cleaned up after the original run.
    """
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    validate_failure_receipt(receipt)
    verify_receipt_hash(receipt)

    case_dict = _reconstruct_failure_case_from_receipt(receipt)
    case = _spec_from_dict(case_dict)

    runner = SandboxRunner(
        sandbox_root=sandbox_root,
        target_repo_name=receipt["target_repo"],
        target_repo_source=target_repo_source,
        source_ref=receipt["target_ref"],
        target_adapter=target_adapter,
    )
    # Re-copy the per-replay workspace under a deterministic id so the replay
    # is isolated from the original run's workspace.
    replay_run_id = f"SR-replay-{receipt['receipt_id']}"
    paths = _ensure_workspace(runner=runner, sandbox_run_id=replay_run_id)
    outcome = run_attack_against_target(workspace=paths, case=case)
    return ReplayResult(
        receipt_id=receipt["receipt_id"],
        matches_original=outcome.actual_result == receipt["actual_result"]
        and outcome.classification == receipt["classification"],
        original_actual_result=receipt["actual_result"],
        replayed_actual_result=outcome.actual_result,
        replayed_classification=outcome.classification,
    )


def _reconstruct_failure_case_from_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Receipts do not store the original FailureCase JSON wholesale, but they
    carry every field needed to reconstruct it for replay.

    For Slice 01 we delegate to the EdgeCaseAgent's default catalog (the
    failure_case_id deterministically maps to a known attack type)."""
    from failureforge.agents.edge_case import EdgeCaseAgent

    agent = EdgeCaseAgent(target_repo=receipt["target_repo"])
    catalog = agent.generate_default_catalog()
    by_id = {c.failure_case_id: c for c in catalog}
    if receipt["failure_case_id"] in by_id:
        return by_id[receipt["failure_case_id"]].to_dict(created_at=receipt["created_at"])
    raise KeyError(
        f"failure_case_id {receipt['failure_case_id']} is not in the default edge-case catalog"
    )


def _spec_from_dict(case: dict[str, Any]) -> FailureCaseSpec:
    return FailureCaseSpec(
        failure_case_id=case["failure_case_id"],
        target_repo=case["target_repo"],
        target_area=case["target_area"],
        invariant=case["invariant"],
        attack_type=case["attack_type"],
        attack_description=case["attack_description"],
        expected_result=case["expected_result"],
        attack_input=case.get("attack_input"),
        agent_lane=case.get("agent_lane", "edge_case"),
    )


def _ensure_workspace(*, runner: SandboxRunner, sandbox_run_id: str) -> Path:
    from failureforge.runtime.sandbox import SandboxPaths

    paths = SandboxPaths.for_run(
        sandbox_root=runner._sandbox_root,  # type: ignore[attr-defined]
        sandbox_run_id=sandbox_run_id,
        target_repo=runner._target_repo_name,  # type: ignore[attr-defined]
    )
    runner._copy_workspace(paths.workspace)  # type: ignore[attr-defined]
    return paths.workspace
