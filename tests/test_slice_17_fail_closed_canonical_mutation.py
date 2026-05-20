"""Slice 17 fail-closed canonical mutation tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from failureforge.agents.edge_case import FailureCaseSpec
from failureforge.runtime import CanonicalSourceMutationError, SandboxRunner
from failureforge.runtime.sandbox import AttackOutcome

_ROOT = Path(__file__).resolve().parents[1]


class _CanonicalMutatingAgent:
    lane = "edge_case"

    def __init__(self, source: Path) -> None:
        self._source = source

    def produce(self, *, workspace: Path, target_repo: str) -> list[AttackOutcome]:
        self._source.joinpath("MUTATED.txt").write_text("bad\n", encoding="utf-8")
        case = FailureCaseSpec(
            failure_case_id="FC-S17-MUTATION",
            target_repo=target_repo,
            target_area="canonical_guard",
            invariant="Sandbox agents must not mutate canonical source.",
            attack_type="state_failure",
            attack_description="Intentionally mutate canonical source.",
            expected_result="Runner fails closed before receipts are accepted.",
            agent_lane=self.lane,
        )
        return [
            AttackOutcome(
                failure_case=case,
                classification="state_failure",
                severity="critical",
                reproducible=False,
                expected_result=case.expected_result,
                actual_result="canonical source was mutated",
                stdout_text="",
                stderr_text="",
                exit_code=5,
            )
        ]


def test_runner_fails_closed_when_canonical_source_hash_changes(tmp_path: Path):
    source = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", source)
    sandbox = tmp_path / "sandbox"
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=source,
    )

    with pytest.raises(CanonicalSourceMutationError) as raised:
        runner.run(
            agents=[_CanonicalMutatingAgent(source)],
            sandbox_run_id="SR-s17-canonical-mutation",
        )

    failed_run = raised.value.sandbox_run
    assert failed_run["status"] == "failed"
    assert failed_run["canonical_source_mutated"] is True
    assert failed_run["receipt_count"] == 0
    assert (
        failed_run["canonical_source_hash_before"]
        != failed_run["canonical_source_hash_after"]
    )

    run_path = sandbox / "runs" / "SR-s17-canonical-mutation" / "sandbox_run.json"
    disk_run = json.loads(run_path.read_text(encoding="utf-8"))
    assert disk_run == failed_run
    assert (sandbox / "runs" / "SR-s17-canonical-mutation" / "exit_code.txt").read_text(
        encoding="utf-8"
    ) == "5\n"
    assert list((sandbox / "receipts").glob("FHR-*.json")) == []
