"""Mutation Agent (Slice 07).

Tests the strength of the existing test/check coverage by intentionally
weakening the target's source. For each known mutation:

1. Read ``registry.py`` from the copied workspace.
2. Apply the mutation (delete or weaken a check).
3. Re-run the relevant edge-case attack.
4. Outcome:
   - if the attack now fails -> the original check exists and works (good).
   - if the attack still passes -> the mutation survived; coverage is weak.

Restores the original source after each mutation so other lanes see a clean
workspace.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from failureforge.agents.edge_case import FailureCaseSpec
from failureforge.runtime.sandbox import AttackOutcome


@dataclass
class _Mutation:
    failure_case_id: str
    invariant: str
    attack_type: str  # uses an existing FailureCase enum
    attack_description: str
    expected_result: str
    snippet: str  # text to delete from registry.py
    attack_input: dict | str


_MUTATIONS: list[_Mutation] = [
    _Mutation(
        failure_case_id="FC-MUTATION-PATH",
        invariant="Path-traversal check must catch `..` paths after mutation.",
        attack_type="bad_path",
        attack_description="Delete the path-traversal guard and confirm bad_path now slips through.",
        expected_result="With the guard deleted, the bad_path attack must NO LONGER raise.",
        snippet=(
            'if "path" in payload:\n'
            '            path = str(payload["path"])\n'
            '            if ".." in path or path.startswith("/"):\n'
            '                raise ValueError(f"unsafe path: {path}")\n'
            '            if "\\x00" in path:\n'
            '                raise ValueError("path contains NUL")'
        ),
        attack_input={
            "key": "K-mutation-path",
            "value": "V",
            "path": "../../etc/passwd",
        },
    ),
    _Mutation(
        failure_case_id="FC-MUTATION-MISSING",
        invariant="Required-field check must reject missing `value` after mutation.",
        attack_type="missing_field",
        attack_description="Delete the missing-value guard and confirm the missing_field attack slips through.",
        expected_result="With the guard deleted, the missing_field attack must NO LONGER raise.",
        snippet=(
            'if "value" not in payload:\n'
            '            raise KeyError("missing required field: value")'
        ),
        attack_input={"key": "K-mutation-missing"},
    ),
]


class MutationAgent:
    lane: str = "mutation"

    def __init__(self, *, target_repo: str, target_area: str = "registry_scan") -> None:
        self._target_repo = target_repo
        self._target_area = target_area

    def produce(self, *, workspace: Path, target_repo: str) -> list[AttackOutcome]:
        outcomes: list[AttackOutcome] = []
        registry_path = workspace / "registry.py"
        if not registry_path.exists():
            return outcomes
        original = registry_path.read_text(encoding="utf-8")
        try:
            for mutation in _MUTATIONS:
                outcomes.append(
                    self._run_mutation(
                        workspace=workspace,
                        registry_path=registry_path,
                        original=original,
                        mutation=mutation,
                    )
                )
        finally:
            registry_path.write_text(original, encoding="utf-8")
        return outcomes

    def _run_mutation(
        self,
        *,
        workspace: Path,
        registry_path: Path,
        original: str,
        mutation: _Mutation,
    ) -> AttackOutcome:
        case = FailureCaseSpec(
            failure_case_id=mutation.failure_case_id,
            target_repo=self._target_repo,
            target_area=self._target_area,
            invariant=mutation.invariant,
            attack_type=mutation.attack_type,
            attack_description=mutation.attack_description,
            expected_result=mutation.expected_result,
            attack_input=mutation.attack_input,
            agent_lane=self.lane,
        )

        if mutation.snippet not in original:
            return AttackOutcome(
                failure_case=case,
                classification="state_failure",
                severity="medium",
                reproducible=True,
                expected_result=case.expected_result,
                actual_result="mutation snippet not found in registry.py — coverage map is stale",
                stdout_text="",
                stderr_text="",
                exit_code=1,
            )

        # Apply mutation by removing the snippet (and a trailing newline if present)
        weakened = original.replace(mutation.snippet + "\n", "").replace(
            mutation.snippet, ""
        )
        registry_path.write_text(weakened, encoding="utf-8")

        # Force a fresh import of the mutated module by purging the cached entry.
        for name, mod in list(sys.modules.items()):
            if name.startswith("_ff_target_") and getattr(mod, "__file__", "").endswith(
                str(registry_path)
            ):
                sys.modules.pop(name)

        from failureforge.runtime.sandbox import run_attack_against_target

        outcome = run_attack_against_target(workspace=workspace, case=case)

        # Re-purge so subsequent agents see the restored canonical source.
        for name, mod in list(sys.modules.items()):
            if name.startswith("_ff_target_") and getattr(mod, "__file__", "").endswith(
                str(registry_path)
            ):
                sys.modules.pop(name)

        # Rewrite the outcome through a mutation-test lens. Note that
        # ``run_attack_against_target`` reports ``no_failure_observed`` when
        # the registry rejects the attack (good defense), and reports the
        # original attack_type when the attack slipped through.
        #
        # So:
        # - attack still rejected after mutation -> defense-in-depth or
        #   snippet drift -> no_failure_observed.
        # - attack slipped through after mutation -> the canonical check was
        #   load-bearing and the mutation killed coverage -> state_failure.
        if outcome.classification != "no_failure_observed":
            actual = (
                "deleting the canonical check let the attack slip through — "
                "test coverage relies on this exact guard"
            )
            return AttackOutcome(
                failure_case=case,
                classification="state_failure",
                severity="high",
                reproducible=True,
                expected_result=case.expected_result,
                actual_result=actual,
                stdout_text=outcome.stdout_text,
                stderr_text=outcome.stderr_text,
                exit_code=outcome.exit_code,
            )
        return AttackOutcome(
            failure_case=case,
            classification="no_failure_observed",
            severity="info",
            reproducible=True,
            expected_result=case.expected_result,
            actual_result="check survived deletion — defense-in-depth or snippet drift",
            stdout_text=outcome.stdout_text,
            stderr_text=outcome.stderr_text,
            exit_code=outcome.exit_code,
        )
