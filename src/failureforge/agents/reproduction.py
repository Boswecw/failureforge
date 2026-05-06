"""Reproduction Agent (Slice 07).

Re-runs each EdgeCaseAgent attack N times against fresh registries and
labels the outcome:

- if every run produces the same actual_result -> reproducible
- if results vary or any run produces no_failure_observed -> intermittent
- if every run is no_failure_observed -> non_reproducible

Reproduction findings are emitted as separate receipts (lane=reproduction)
so cross-agent agreement against the original edge_case findings can boost
confidence at scoring time.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from failureforge.agents.edge_case import EdgeCaseAgent, FailureCaseSpec
from failureforge.runtime.sandbox import AttackOutcome, run_attack_against_target


class ReproductionAgent:
    lane: str = "reproduction"

    def __init__(
        self,
        *,
        target_repo: str,
        target_area: str = "registry_scan",
        repeats: int = 3,
    ) -> None:
        self._target_repo = target_repo
        self._target_area = target_area
        self._repeats = max(2, repeats)

    def produce(self, *, workspace: Path, target_repo: str) -> list[AttackOutcome]:
        catalog = EdgeCaseAgent(
            target_repo=self._target_repo, target_area=self._target_area
        ).generate_default_catalog()
        outcomes: list[AttackOutcome] = []
        for spec in catalog:
            outcomes.append(self._reproduce(workspace, spec))
        return outcomes

    def _reproduce(self, workspace: Path, original: FailureCaseSpec) -> AttackOutcome:
        actuals: list[str] = []
        classifications: Counter[str] = Counter()
        last_outcome: AttackOutcome | None = None
        for _ in range(self._repeats):
            run_outcome = run_attack_against_target(workspace=workspace, case=original)
            last_outcome = run_outcome
            actuals.append(run_outcome.actual_result)
            classifications[run_outcome.classification] += 1
        assert last_outcome is not None

        unique_actuals = set(actuals)
        if len(unique_actuals) == 1 and "no_failure_observed" not in classifications:
            classification = last_outcome.classification
            severity = last_outcome.severity
            reproducible = True
            actual = (
                f"deterministic across {self._repeats} runs: {actuals[0]}"
            )
        elif "no_failure_observed" in classifications and len(classifications) > 1:
            classification = last_outcome.classification
            severity = "medium"
            reproducible = False
            actual = (
                f"intermittent across {self._repeats} runs: outcomes={dict(classifications)}"
            )
        else:
            classification = last_outcome.classification
            severity = "info" if classification == "no_failure_observed" else "low"
            reproducible = classification != "no_failure_observed"
            actual = (
                f"stable but {'non-reproducible' if not reproducible else 'reproducible'} "
                f"across {self._repeats} runs"
            )

        spec = FailureCaseSpec(
            failure_case_id=f"FC-REPRO-{original.failure_case_id}",
            target_repo=self._target_repo,
            target_area=self._target_area,
            invariant=original.invariant,
            attack_type=original.attack_type,
            attack_description=(
                f"Reproduction of {original.failure_case_id}: re-run {self._repeats} times "
                f"and check determinism."
            ),
            expected_result=original.expected_result,
            attack_input=original.attack_input,
            agent_lane=self.lane,
        )

        return AttackOutcome(
            failure_case=spec,
            classification=classification,
            severity=severity,
            reproducible=reproducible,
            expected_result=original.expected_result,
            actual_result=actual,
            stdout_text="\n".join(actuals),
            stderr_text="",
            exit_code=0,
        )
