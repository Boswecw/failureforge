"""SandboxRunner — copies a target repo into an isolated workspace, runs the
edge-case agent's attack catalog against the copy, and emits SandboxRun and
FailureHarvestReceipt JSON artifacts.

Doctrine constraints:

- The runner only writes inside the per-run workspace and the sandbox/{runs,
  receipts,reports} directories. It must NEVER touch the canonical target.
- Failures produce a FailureHarvestReceipt with both expected_result and
  actual_result, a reproducibility flag, and a replay command.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from failureforge.agents.edge_case import EdgeCaseAgent, FailureCaseSpec
from failureforge.runtime.target_loader import load_registry_module
from failureforge.validation import (
    apply_receipt_hash,
    validate_failure_case,
    validate_failure_receipt,
    validate_sandbox_run,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _stable_id(prefix: str, *parts: str) -> str:
    import hashlib

    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


@dataclass
class SandboxPaths:
    """Paths the runner uses. The runner refuses to write outside these."""

    sandbox_root: Path  # e.g. failureforge/sandbox/
    workspace: Path
    run_dir: Path
    receipts_dir: Path
    reports_dir: Path

    @classmethod
    def for_run(cls, *, sandbox_root: Path, sandbox_run_id: str, target_repo: str) -> "SandboxPaths":
        ws = sandbox_root / "workspaces" / sandbox_run_id / target_repo
        run_dir = sandbox_root / "runs" / sandbox_run_id
        receipts_dir = sandbox_root / "receipts"
        reports_dir = sandbox_root / "reports"
        for d in (ws.parent, run_dir, receipts_dir, reports_dir):
            d.mkdir(parents=True, exist_ok=True)
        return cls(
            sandbox_root=sandbox_root,
            workspace=ws,
            run_dir=run_dir,
            receipts_dir=receipts_dir,
            reports_dir=reports_dir,
        )


@dataclass
class AttackOutcome:
    failure_case: FailureCaseSpec
    classification: str
    severity: str
    reproducible: bool
    expected_result: str
    actual_result: str
    stdout_text: str
    stderr_text: str
    exit_code: int | None


def run_attack_against_target(
    *,
    workspace: Path,
    case: FailureCaseSpec,
) -> AttackOutcome:
    """Run a single edge-case attack against the copied workspace's registry module.

    Returns an ``AttackOutcome`` with classification + actual_result.
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    actual: str
    classification = case.attack_type
    severity = "high"
    reproducible = True

    try:
        registry_mod = load_registry_module(workspace)
    except Exception as exc:  # noqa: BLE001
        return AttackOutcome(
            failure_case=case,
            classification="state_failure",
            severity="critical",
            reproducible=False,
            expected_result=case.expected_result,
            actual_result=f"failed to load registry module: {exc!r}",
            stdout_text="",
            stderr_text=traceback.format_exc(),
            exit_code=2,
        )

    Registry = getattr(registry_mod, "Registry", None)
    if Registry is None:
        return AttackOutcome(
            failure_case=case,
            classification="state_failure",
            severity="critical",
            reproducible=False,
            expected_result=case.expected_result,
            actual_result="target workspace has no Registry class",
            stdout_text="",
            stderr_text="",
            exit_code=2,
        )

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            registry = Registry()

            if case.attack_type == "duplicate_replay":
                first = registry.upsert(case.attack_input)
                second = registry.upsert(case.attack_input)
                # Invariant: duplicate must not create duplicate record.
                # If the registry has the bug, second_id != first_id and
                # registry.size() == 2.
                if first == second and registry.size() == 1:
                    classification = "no_failure_observed"
                    severity = "info"
                    actual = "duplicate input was deduplicated as expected"
                else:
                    actual = (
                        f"duplicate input created a new record: "
                        f"first_id={first!r} second_id={second!r} size={registry.size()}"
                    )
            elif case.attack_type == "missing_field":
                try:
                    registry.upsert(case.attack_input)
                    actual = (
                        "registry accepted a record missing the required `value` field"
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    classification = "no_failure_observed"
                    severity = "info"
                    actual = f"registry rejected as expected: {exc!r}"
            elif case.attack_type == "unknown_enum":
                try:
                    registry.upsert(case.attack_input)
                    actual = (
                        "registry accepted an unknown enum value in `kind`"
                    )
                except (ValueError, KeyError) as exc:
                    classification = "no_failure_observed"
                    severity = "info"
                    actual = f"registry rejected as expected: {exc!r}"
            elif case.attack_type == "bad_path":
                try:
                    registry.upsert(case.attack_input)
                    actual = (
                        "registry accepted a path containing traversal escape"
                    )
                except (ValueError, OSError) as exc:
                    classification = "no_failure_observed"
                    severity = "info"
                    actual = f"registry rejected as expected: {exc!r}"
            elif case.attack_type == "bad_unicode":
                try:
                    registry.upsert(case.attack_input)
                    if any(
                        "\x00" in v for v in registry.dump().values() if isinstance(v, str)
                    ):
                        actual = "registry stored a NUL byte unsanitised"
                    else:
                        classification = "no_failure_observed"
                        severity = "info"
                        actual = "NUL byte was sanitized or rejected"
                except (ValueError, UnicodeError) as exc:
                    classification = "no_failure_observed"
                    severity = "info"
                    actual = f"registry rejected as expected: {exc!r}"
            elif case.attack_type == "malformed_input":
                try:
                    registry.upsert(case.attack_input)
                    actual = "registry accepted a non-mapping input"
                except (TypeError, ValueError, AttributeError) as exc:
                    classification = "no_failure_observed"
                    severity = "info"
                    actual = f"registry rejected as expected: {exc!r}"
            else:
                actual = f"unsupported attack_type for edge_case agent: {case.attack_type}"
                classification = "no_failure_observed"
                severity = "low"
        exit_code = 0
    except Exception as exc:  # noqa: BLE001
        actual = f"unhandled exception in target: {exc!r}"
        classification = "state_failure"
        severity = "critical"
        exit_code = 1

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


class SandboxRunner:
    """Top-level orchestrator: copies workspace, runs the agent's catalog,
    writes the SandboxRun + FailureHarvestReceipt artifacts."""

    def __init__(
        self,
        *,
        sandbox_root: Path,
        target_repo_name: str,
        target_repo_source: Path,
        source_ref: str = "local",
    ) -> None:
        self._sandbox_root = sandbox_root.resolve()
        self._target_repo_name = target_repo_name
        self._target_repo_source = target_repo_source.resolve()
        self._source_ref = source_ref

        if not self._target_repo_source.exists():
            raise FileNotFoundError(
                f"target repo source does not exist: {self._target_repo_source}"
            )
        # Hard rule: target_repo_source must NOT live underneath the sandbox.
        try:
            self._target_repo_source.relative_to(self._sandbox_root)
        except ValueError:
            pass
        else:
            raise ValueError(
                "refusing to use a target inside the sandbox tree as the canonical source"
            )

    def run(
        self,
        *,
        agent: EdgeCaseAgent | None = None,
        agents: list[Any] | None = None,
        sandbox_run_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute the agent's catalog (Slice 01) or run a list of lane agents
        (Slice 07). Returns the in-memory SandboxRun record. Side effect:
        writes SandboxRun + N receipt JSON files.

        ``agent`` is the legacy single-agent slot (defaults to ``EdgeCaseAgent``).
        ``agents`` is the Slice 07 multi-lane slot — when supplied, each agent
        is invoked via ``agent.produce(workspace, target_repo)`` and its
        outcomes become receipts tagged with ``agent.lane``.
        """
        run_id = sandbox_run_id or _stable_id(
            "SR", self._target_repo_name, _utc_now(), str(id(self))
        )
        paths = SandboxPaths.for_run(
            sandbox_root=self._sandbox_root,
            sandbox_run_id=run_id,
            target_repo=self._target_repo_name,
        )
        self._copy_workspace(paths.workspace)

        if agents is None:
            agents = [agent or EdgeCaseAgent(target_repo=self._target_repo_name)]
        lanes = sorted({getattr(a, "lane", "edge_case") for a in agents})

        sandbox_run = {
            "schema_version": "SandboxRun.v1",
            "sandbox_run_id": run_id,
            "target_repo": self._target_repo_name,
            "source_ref": self._source_ref,
            "workspace_path": str(paths.workspace.relative_to(self._sandbox_root.parent)),
            "agent_lanes": lanes,
            "started_at": _utc_now(),
            "completed_at": None,
            "status": "running",
            "receipt_count": 0,
        }
        validate_sandbox_run(sandbox_run)
        (paths.run_dir / "sandbox_run.json").write_text(
            json.dumps(sandbox_run, indent=2, sort_keys=True), encoding="utf-8"
        )

        receipt_paths: list[Path] = []
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        for agent_obj in agents:
            lane = getattr(agent_obj, "lane", "edge_case")
            outcomes = self._invoke_agent(agent_obj, paths.workspace)
            for outcome in outcomes:
                # Re-tag the failure case to the agent's lane in case it was
                # left as the default.
                outcome.failure_case.agent_lane = lane
                case_dict = outcome.failure_case.to_dict()
                validate_failure_case(case_dict)
                stdout_chunks.append(
                    f"[{lane}/{outcome.failure_case.failure_case_id}] "
                    f"{outcome.failure_case.attack_type}\n{outcome.stdout_text}"
                )
                stderr_chunks.append(
                    f"[{lane}/{outcome.failure_case.failure_case_id}] "
                    f"{outcome.failure_case.attack_type}\n{outcome.stderr_text}"
                )
                receipt_paths.append(self._write_receipt(paths, run_id, outcome))

        (paths.run_dir / "stdout.log").write_text("\n".join(stdout_chunks), encoding="utf-8")
        (paths.run_dir / "stderr.log").write_text("\n".join(stderr_chunks), encoding="utf-8")
        (paths.run_dir / "exit_code.txt").write_text("0\n", encoding="utf-8")

        sandbox_run["completed_at"] = _utc_now()
        sandbox_run["status"] = "completed"
        sandbox_run["receipt_count"] = len(receipt_paths)
        validate_sandbox_run(sandbox_run)
        (paths.run_dir / "sandbox_run.json").write_text(
            json.dumps(sandbox_run, indent=2, sort_keys=True), encoding="utf-8"
        )
        return {"sandbox_run": sandbox_run, "receipt_paths": [str(p) for p in receipt_paths], "paths": paths}

    def _invoke_agent(self, agent_obj: Any, workspace: Path) -> list[AttackOutcome]:
        # Back-compat shim: legacy EdgeCaseAgent has ``generate_default_catalog``;
        # Slice 07 agents implement ``produce``. Prefer ``produce`` when present.
        if hasattr(agent_obj, "produce"):
            return agent_obj.produce(workspace=workspace, target_repo=self._target_repo_name)
        outcomes: list[AttackOutcome] = []
        for spec in agent_obj.generate_default_catalog():
            outcomes.append(run_attack_against_target(workspace=workspace, case=spec))
        return outcomes

    # ---- internals ----

    def _copy_workspace(self, dest: Path) -> None:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self._target_repo_source, dest)

    def _write_receipt(self, paths: SandboxPaths, run_id: str, outcome: AttackOutcome) -> Path:
        receipt_id = _stable_id("FHR", run_id, outcome.failure_case.failure_case_id)
        repro_command = (
            f"./scripts/replay_failure.sh sandbox/receipts/{receipt_id}.json"
        )
        receipt = {
            "schema_version": "FailureHarvestReceipt.v1",
            "receipt_id": receipt_id,
            "failure_case_id": outcome.failure_case.failure_case_id,
            "sandbox_run_id": run_id,
            "target_repo": self._target_repo_name,
            "target_ref": self._source_ref,
            "classification": outcome.classification,
            "severity": outcome.severity,
            "expected_result": outcome.expected_result,
            "actual_result": outcome.actual_result,
            "reproducible": outcome.reproducible,
            "repro_command": repro_command,
            "artifact_paths": [
                str((paths.run_dir / "stdout.log").relative_to(self._sandbox_root.parent)),
                str((paths.run_dir / "stderr.log").relative_to(self._sandbox_root.parent)),
            ],
            "promotion_status": "pending_operator_review",
            "created_at": _utc_now(),
            "agent_lane": outcome.failure_case.agent_lane,
            "stdout_excerpt": outcome.stdout_text[:8000],
            "stderr_excerpt": outcome.stderr_text[:8000],
            "exit_code": outcome.exit_code,
        }
        sealed = apply_receipt_hash(receipt)
        validate_failure_receipt(sealed)
        out = paths.receipts_dir / f"{receipt_id}.json"
        out.write_text(json.dumps(sealed, indent=2, sort_keys=True), encoding="utf-8")
        return out


def list_receipts(sandbox_root: Path) -> Iterable[Path]:
    receipts_dir = sandbox_root / "receipts"
    if not receipts_dir.exists():
        return []
    return sorted(p for p in receipts_dir.glob("FHR-*.json"))
