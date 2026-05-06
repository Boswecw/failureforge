"""Edge-Case Agent (Slice 01).

Generates malformed-input, duplicate-replay, missing-field, unknown-enum,
bad-path, and bad-unicode FailureCase.v1 records and runs each against the
sandbox-copied workspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from failureforge.runtime.sandbox import AttackOutcome


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass
class FailureCaseSpec:
    """A single planned attack case."""

    failure_case_id: str
    target_repo: str
    target_area: str
    invariant: str
    attack_type: str
    attack_description: str
    expected_result: str
    attack_input: Any | None = None
    agent_lane: str = "edge_case"

    def to_dict(self, *, created_at: str | None = None) -> dict[str, Any]:
        body = {
            "schema_version": "FailureCase.v1",
            "failure_case_id": self.failure_case_id,
            "target_repo": self.target_repo,
            "target_area": self.target_area,
            "invariant": self.invariant,
            "attack_type": self.attack_type,
            "attack_description": self.attack_description,
            "expected_result": self.expected_result,
            "agent_lane": self.agent_lane,
            "created_at": created_at or _utc_now(),
        }
        if self.attack_input is not None:
            body["attack_input"] = self.attack_input
        return body


class EdgeCaseAgent:
    """Generates a default catalog of edge-case attacks for a target."""

    def __init__(self, *, target_repo: str, target_area: str = "registry_scan") -> None:
        self._target_repo = target_repo
        self._target_area = target_area

    def generate_default_catalog(
        self, *, id_factory: Callable[[int], str] | None = None
    ) -> list[FailureCaseSpec]:
        idgen = id_factory or (lambda i: f"FC-{i:04d}")
        cases: list[FailureCaseSpec] = []

        cases.append(
            FailureCaseSpec(
                failure_case_id=idgen(1),
                target_repo=self._target_repo,
                target_area=self._target_area,
                invariant="Duplicate input must not create duplicate canonical records.",
                attack_type="duplicate_replay",
                attack_description="Submit the same input twice with the same idempotency key and assert the second call does not create a new record.",
                expected_result="Existing result reused or duplicate rejected.",
                attack_input={"key": "K1", "value": "V1"},
            )
        )
        cases.append(
            FailureCaseSpec(
                failure_case_id=idgen(2),
                target_repo=self._target_repo,
                target_area=self._target_area,
                invariant="Records missing required fields must be rejected.",
                attack_type="missing_field",
                attack_description="Submit a record without its required `value` field.",
                expected_result="ValueError or rejection.",
                attack_input={"key": "K2"},  # missing 'value'
            )
        )
        cases.append(
            FailureCaseSpec(
                failure_case_id=idgen(3),
                target_repo=self._target_repo,
                target_area=self._target_area,
                invariant="Unknown enum values must be rejected.",
                attack_type="unknown_enum",
                attack_description="Submit a record with an unknown `kind` enum value.",
                expected_result="ValueError or rejection.",
                attack_input={"key": "K3", "value": "V3", "kind": "not_an_allowed_kind"},
            )
        )
        cases.append(
            FailureCaseSpec(
                failure_case_id=idgen(4),
                target_repo=self._target_repo,
                target_area=self._target_area,
                invariant="Path inputs must reject traversal escapes.",
                attack_type="bad_path",
                attack_description="Submit a path containing `../../etc/passwd` and assert it is rejected.",
                expected_result="Path rejected with safety error.",
                attack_input={"key": "K4", "value": "V4", "path": "../../etc/passwd"},
            )
        )
        cases.append(
            FailureCaseSpec(
                failure_case_id=idgen(5),
                target_repo=self._target_repo,
                target_area=self._target_area,
                invariant="Inputs must accept valid Unicode and reject control characters.",
                attack_type="bad_unicode",
                attack_description="Submit input containing a NUL character.",
                expected_result="Sanitized or rejected.",
                attack_input={"key": "K5", "value": "V\x00ALUE"},
            )
        )
        cases.append(
            FailureCaseSpec(
                failure_case_id=idgen(6),
                target_repo=self._target_repo,
                target_area=self._target_area,
                invariant="Malformed JSON must not crash the registry.",
                attack_type="malformed_input",
                attack_description="Submit a non-JSON-coerceable object as input.",
                expected_result="Validation error, registry remains stable.",
                attack_input="not-a-mapping",
            )
        )
        return cases


    # Slice 07 — protocol surface so SandboxRunner can drive multiple lanes
    # uniformly. Each FailureCase becomes one AttackOutcome via the existing
    # ``run_attack_against_target`` helper.
    lane: str = "edge_case"

    def produce(self, *, workspace: Path, target_repo: str) -> list["AttackOutcome"]:
        from failureforge.runtime.sandbox import run_attack_against_target

        outcomes: list["AttackOutcome"] = []
        for spec in self.generate_default_catalog():
            outcomes.append(run_attack_against_target(workspace=workspace, case=spec))
        return outcomes
