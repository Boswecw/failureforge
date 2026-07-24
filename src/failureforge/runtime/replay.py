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
from failureforge.runtime.sandbox import (
    CanonicalSourceMutationError,
    SandboxPaths,
    SandboxRunner,
    _hash_tree,
    _utc_now,
    run_attack_against_target,
)
from failureforge.validation import (
    validate_failure_receipt,
    validate_sandbox_run,
    verify_receipt_hash,
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
    replay_run_id = f"SR-replay-{receipt['receipt_id']}"
    canonical_source = runner._target_repo_source  # type: ignore[attr-defined]
    canonical_hash_before = _hash_tree(canonical_source)
    paths = _ensure_workspace(runner=runner, sandbox_run_id=replay_run_id)
    replay_run = _build_replay_run(
        receipt=receipt,
        case=case,
        paths=paths,
        sandbox_run_id=replay_run_id,
        canonical_hash_before=canonical_hash_before,
    )
    _write_replay_run(paths=paths, sandbox_run=replay_run)

    outcome = run_attack_against_target(workspace=paths.workspace, case=case)
    (paths.run_dir / "stdout.log").write_text(outcome.stdout_text, encoding="utf-8")
    (paths.run_dir / "stderr.log").write_text(outcome.stderr_text, encoding="utf-8")

    canonical_hash_after = _hash_tree(canonical_source)
    replay_run["completed_at"] = _utc_now()
    replay_run["canonical_source_hash_after"] = canonical_hash_after
    replay_run["canonical_source_mutated"] = (
        canonical_hash_after != canonical_hash_before
    )
    if replay_run["canonical_source_mutated"]:
        replay_run["status"] = "failed"
        (paths.run_dir / "exit_code.txt").write_text("5\n", encoding="utf-8")
        _write_replay_run(paths=paths, sandbox_run=replay_run)
        raise CanonicalSourceMutationError(replay_run)

    matches_original = (
        outcome.actual_result == receipt["actual_result"]
        and outcome.classification == receipt["classification"]
    )
    replay_run["status"] = "completed" if matches_original else "failed"
    (paths.run_dir / "exit_code.txt").write_text(
        "0\n" if matches_original else "2\n", encoding="utf-8"
    )
    _write_replay_run(paths=paths, sandbox_run=replay_run)

    return ReplayResult(
        receipt_id=receipt["receipt_id"],
        matches_original=matches_original,
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
        return by_id[receipt["failure_case_id"]].to_dict(
            created_at=receipt["created_at"]
        )
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


def _ensure_workspace(*, runner: SandboxRunner, sandbox_run_id: str) -> SandboxPaths:
    paths = SandboxPaths.for_run(
        sandbox_root=runner._sandbox_root,  # type: ignore[attr-defined]
        sandbox_run_id=sandbox_run_id,
        target_repo=runner._target_repo_name,  # type: ignore[attr-defined]
    )
    runner._copy_workspace(paths.workspace)  # type: ignore[attr-defined]
    return paths


def _build_replay_run(
    *,
    receipt: dict[str, Any],
    case: FailureCaseSpec,
    paths: SandboxPaths,
    sandbox_run_id: str,
    canonical_hash_before: str,
) -> dict[str, Any]:
    sandbox_run = {
        "schema_version": "SandboxRun.v1",
        "sandbox_run_id": sandbox_run_id,
        "target_repo": receipt["target_repo"],
        "source_ref": receipt["target_ref"],
        "workspace_path": str(paths.workspace.relative_to(paths.sandbox_root.parent)),
        "agent_lanes": [case.agent_lane],
        "started_at": _utc_now(),
        "completed_at": None,
        "status": "running",
        "receipt_count": 0,
        "canonical_source_hash_before": canonical_hash_before,
        "canonical_source_hash_after": None,
        "canonical_source_mutated": None,
    }
    validate_sandbox_run(sandbox_run)
    return sandbox_run


def _write_replay_run(*, paths: SandboxPaths, sandbox_run: dict[str, Any]) -> None:
    validate_sandbox_run(sandbox_run)
    (paths.run_dir / "sandbox_run.json").write_text(
        json.dumps(sandbox_run, indent=2, sort_keys=True), encoding="utf-8"
    )
