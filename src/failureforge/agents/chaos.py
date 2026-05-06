"""Chaos Agent (Slice 07).

Simulates timeout, partial-write, and crash-during-write conditions against
the registry. Reuses the sandbox-copied workspace so canonical state is
never touched.
"""

from __future__ import annotations

import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from failureforge.agents.edge_case import FailureCaseSpec
from failureforge.runtime.sandbox import AttackOutcome
from failureforge.runtime.target_loader import load_registry_module


class _SimulatedTimeoutError(Exception):
    """Wrapped timeout — uses a private class so target except-clauses
    designed for ``TimeoutError`` won't swallow the chaos signal silently."""


class ChaosAgent:
    lane: str = "chaos"

    def __init__(self, *, target_repo: str, target_area: str = "registry_runtime") -> None:
        self._target_repo = target_repo
        self._target_area = target_area

    def produce(self, *, workspace: Path, target_repo: str) -> list[AttackOutcome]:
        outcomes: list[AttackOutcome] = []
        outcomes.append(self._timeout_attack(workspace))
        outcomes.append(self._partial_write_attack(workspace))
        outcomes.append(self._crash_during_write_attack(workspace))
        return outcomes

    # ---- attacks ----

    def _timeout_attack(self, workspace: Path) -> AttackOutcome:
        case = FailureCaseSpec(
            failure_case_id="FC-CHAOS-TIMEOUT",
            target_repo=self._target_repo,
            target_area=self._target_area,
            invariant="A timeout in upsert must not corrupt persisted state.",
            attack_type="state_failure",
            attack_description="Patch upsert to raise TimeoutError mid-call; check registry state.",
            expected_result="Either no record was added or the record is fully formed; never partial.",
            attack_input={"key": "K-chaos-timeout", "value": "V"},
            agent_lane=self.lane,
        )
        return self._run_with_patch(
            workspace=workspace,
            case=case,
            patch_kind="timeout",
        )

    def _partial_write_attack(self, workspace: Path) -> AttackOutcome:
        case = FailureCaseSpec(
            failure_case_id="FC-CHAOS-PARTIAL",
            target_repo=self._target_repo,
            target_area=self._target_area,
            invariant="A partial write must not leave a record missing required fields.",
            attack_type="state_failure",
            attack_description="Inject a partial write that drops the `value` field after upsert returns.",
            expected_result="Stored record retains `value`; size invariant holds.",
            attack_input={"key": "K-chaos-partial", "value": "V"},
            agent_lane=self.lane,
        )
        return self._run_with_patch(
            workspace=workspace,
            case=case,
            patch_kind="partial",
        )

    def _crash_during_write_attack(self, workspace: Path) -> AttackOutcome:
        case = FailureCaseSpec(
            failure_case_id="FC-CHAOS-CRASH",
            target_repo=self._target_repo,
            target_area=self._target_area,
            invariant="A mid-write exception must not corrupt the registry.",
            attack_type="state_failure",
            attack_description="Raise after _records is mutated but before _counter increments.",
            expected_result="size() reflects committed records only; no orphaned counter.",
            attack_input={"key": "K-chaos-crash", "value": "V"},
            agent_lane=self.lane,
        )
        return self._run_with_patch(
            workspace=workspace,
            case=case,
            patch_kind="crash",
        )

    # ---- runner ----

    def _run_with_patch(
        self,
        *,
        workspace: Path,
        case: FailureCaseSpec,
        patch_kind: str,
    ) -> AttackOutcome:
        registry_mod = load_registry_module(workspace)
        Registry = getattr(registry_mod, "Registry")

        registry = Registry()
        # Drive a single baseline upsert so we have a reference state.
        baseline_id = registry.upsert({"key": "K-baseline", "value": "B"})
        baseline_size = registry.size()

        original_upsert = Registry.upsert

        def _patched(self_inst, payload):  # noqa: ANN001
            if patch_kind == "timeout":
                raise _SimulatedTimeoutError("simulated timeout in upsert")
            if patch_kind == "partial":
                # Run the original then strip `value` from the freshly-written
                # record to model a write that returned but committed half.
                rid = original_upsert(self_inst, payload)
                self_inst._records[rid].pop("value", None)  # noqa: SLF001
                return rid
            if patch_kind == "crash":
                # Mutate first, then crash before returning.
                original_upsert(self_inst, payload)
                raise RuntimeError("simulated crash mid-write")
            return original_upsert(self_inst, payload)

        Registry.upsert = _patched  # type: ignore[assignment]

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        actual: str
        classification = "state_failure"
        severity = "high"
        reproducible = True
        exit_code = 0

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                try:
                    registry.upsert(case.attack_input)
                except _SimulatedTimeoutError:
                    if registry.size() != baseline_size:
                        actual = (
                            "registry committed a record despite a simulated timeout — "
                            "state is not transactional"
                        )
                    else:
                        actual = "registry recovered cleanly from a simulated timeout"
                        classification = "no_failure_observed"
                        severity = "info"
                except RuntimeError as exc:
                    if registry.size() != baseline_size:
                        actual = (
                            f"registry committed a record despite a mid-write crash: {exc!r}"
                        )
                    else:
                        actual = f"registry recovered cleanly from a mid-write crash: {exc!r}"
                        classification = "no_failure_observed"
                        severity = "info"
                else:
                    if patch_kind == "partial":
                        # The patched upsert succeeded; check that the persisted
                        # record still has its `value`.
                        good = all(
                            "value" in rec
                            for rec in registry.dump().values()
                        )
                        if good:
                            actual = "registry preserved required fields after a simulated partial write"
                            classification = "no_failure_observed"
                            severity = "info"
                        else:
                            actual = (
                                "registry retained a partially-written record missing `value`"
                            )
                    else:
                        actual = "patched upsert returned without raising; baseline check pending"
                        classification = "no_failure_observed"
                        severity = "info"
        finally:
            Registry.upsert = original_upsert  # type: ignore[assignment]

        return AttackOutcome(
            failure_case=case,
            classification=classification,
            severity=severity,
            reproducible=reproducible,
            expected_result=case.expected_result,
            actual_result=actual,
            stdout_text=stdout_buf.getvalue(),
            stderr_text=stderr_buf.getvalue(),
            exit_code=exit_code,
        )
