"""Classification Agent (Slice 07).

Reads a list of receipts (or runs the edge-case attacks itself) and emits
deterministic classification refinements:

- duplicate_replay state failures escalate to ``critical`` because they are
  unbounded growth invariants; baseline severity in Slice 01 was ``high``.
- bad_path / bad_unicode / malformed_input / missing_field / unknown_enum
  receipts that ARE reproducible state failures stay at the producer's
  severity but get an explicit classifier-asserted severity field on the
  receipt outcome.
- no_failure_observed cases stay at ``info``.

The agent is deterministic — it never depends on a model. The plan §08
requires it: "No LLM-only classification without deterministic metadata."
"""

from __future__ import annotations

from pathlib import Path

from failureforge.agents.edge_case import EdgeCaseAgent, FailureCaseSpec
from failureforge.runtime.sandbox import AttackOutcome, run_attack_against_target

_CLASSIFIER_RULES: dict[str, tuple[str, str]] = {
    # attack_type -> (escalated_severity_for_real_failure, recommended_label)
    "duplicate_replay": ("critical", "unbounded_growth"),
    "missing_field": ("high", "input_contract_break"),
    "unknown_enum": ("high", "input_contract_break"),
    "bad_path": ("high", "path_traversal"),
    "bad_unicode": ("medium", "input_sanitisation"),
    "malformed_input": ("medium", "input_validation"),
}


class ClassificationAgent:
    lane: str = "classification"

    def __init__(self, *, target_repo: str, target_area: str = "registry_scan") -> None:
        self._target_repo = target_repo
        self._target_area = target_area

    def produce(self, *, workspace: Path, target_repo: str) -> list[AttackOutcome]:
        catalog = EdgeCaseAgent(
            target_repo=self._target_repo, target_area=self._target_area
        ).generate_default_catalog()
        outcomes: list[AttackOutcome] = []
        for spec in catalog:
            base = run_attack_against_target(workspace=workspace, case=spec)
            outcomes.append(self._classify(base, spec))
        return outcomes

    def classify_outcome(self, outcome: AttackOutcome) -> AttackOutcome:
        """Public classifier entry — used by tests + by external callers that
        already have raw outcomes."""
        return self._classify(outcome, outcome.failure_case)

    def _classify(self, outcome: AttackOutcome, original: FailureCaseSpec) -> AttackOutcome:
        rule = _CLASSIFIER_RULES.get(original.attack_type)
        if outcome.classification == "no_failure_observed" or rule is None:
            severity = "info" if outcome.classification == "no_failure_observed" else outcome.severity
            label = "no_failure_observed" if outcome.classification == "no_failure_observed" else "unclassified"
            actual = f"{outcome.actual_result} | classifier_label={label}"
            spec = FailureCaseSpec(
                failure_case_id=f"FC-CLASS-{original.failure_case_id}",
                target_repo=self._target_repo,
                target_area=self._target_area,
                invariant=original.invariant,
                attack_type=original.attack_type,
                attack_description=(
                    f"Classification refinement of {original.failure_case_id}."
                ),
                expected_result=original.expected_result,
                attack_input=original.attack_input,
                agent_lane=self.lane,
            )
            return AttackOutcome(
                failure_case=spec,
                classification=outcome.classification,
                severity=severity,
                reproducible=outcome.reproducible,
                expected_result=outcome.expected_result,
                actual_result=actual,
                stdout_text=outcome.stdout_text,
                stderr_text=outcome.stderr_text,
                exit_code=outcome.exit_code,
            )

        new_severity, label = rule
        spec = FailureCaseSpec(
            failure_case_id=f"FC-CLASS-{original.failure_case_id}",
            target_repo=self._target_repo,
            target_area=self._target_area,
            invariant=original.invariant,
            attack_type=original.attack_type,
            attack_description=(
                f"Classification refinement of {original.failure_case_id}: "
                f"label={label}, escalated severity={new_severity}."
            ),
            expected_result=original.expected_result,
            attack_input=original.attack_input,
            agent_lane=self.lane,
        )
        actual = f"{outcome.actual_result} | classifier_label={label}"
        return AttackOutcome(
            failure_case=spec,
            classification=outcome.classification,
            severity=new_severity,
            reproducible=outcome.reproducible,
            expected_result=outcome.expected_result,
            actual_result=actual,
            stdout_text=outcome.stdout_text,
            stderr_text=outcome.stderr_text,
            exit_code=outcome.exit_code,
        )
