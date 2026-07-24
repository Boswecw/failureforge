"""Slice 11 target-adapter guard tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from failureforge.runtime import (
    SandboxRunner,
    TargetAdapterError,
    load_target_adapter,
    validate_target_adapter_for_source,
)
from failureforge.validation import SchemaValidationError, validate_target_adapter

_ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads((_ROOT / path).read_text(encoding="utf-8"))


def _valid_adapter() -> dict:
    return _load("fixtures/valid/TargetAdapter.v1.valid.json")


def test_target_adapter_valid_fixture_validates():
    validate_target_adapter(_valid_adapter())


@pytest.mark.parametrize(
    "fixture",
    [
        "fixtures/invalid/TargetAdapter.v1.unsupported-attack-family.json",
        "fixtures/invalid/TargetAdapter.v1.guard-disabled.json",
    ],
)
def test_target_adapter_invalid_fixtures_fail(fixture: str):
    with pytest.raises(SchemaValidationError):
        validate_target_adapter(_load(fixture))


def test_target_adapter_guard_accepts_canonical_source_outside_sandbox(tmp_path: Path):
    adapter = _valid_adapter()
    source = _ROOT / "sandbox-targets" / "example-repo"

    checked = validate_target_adapter_for_source(
        adapter,
        target_repo_source=source,
        sandbox_root=tmp_path / "sandbox",
    )

    assert checked["adapter_id"] == "TA-example-repo"


def test_target_adapter_guard_rejects_mismatched_target(tmp_path: Path):
    adapter = _valid_adapter()
    adapter["target_repo"] = "other-repo"

    with pytest.raises(TargetAdapterError, match="target_repo"):
        validate_target_adapter_for_source(
            adapter,
            target_repo_source=_ROOT / "sandbox-targets" / "example-repo",
            sandbox_root=tmp_path / "sandbox",
        )


def test_target_adapter_guard_rejects_source_inside_sandbox(tmp_path: Path):
    adapter = _valid_adapter()
    source = tmp_path / "sandbox" / "example-repo"
    source.mkdir(parents=True)

    with pytest.raises(TargetAdapterError, match="outside the sandbox"):
        validate_target_adapter_for_source(
            adapter,
            target_repo_source=source,
            sandbox_root=tmp_path / "sandbox",
        )


def test_sandbox_runner_accepts_valid_target_adapter(tmp_path: Path):
    adapter = load_target_adapter(_ROOT / "fixtures/valid/TargetAdapter.v1.valid.json")
    sandbox = tmp_path / "sandbox"
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_ROOT / "sandbox-targets" / "example-repo",
        target_adapter=adapter,
    )

    result = runner.run(sandbox_run_id="SR-target-adapter")

    assert result["sandbox_run"]["status"] == "completed"
    assert result["receipt_paths"]


def test_sandbox_runner_preflights_adapter_attack_family_before_copy(tmp_path: Path):
    adapter = _valid_adapter()
    adapter["supported_attack_families"] = ["duplicate_replay"]
    sandbox = tmp_path / "sandbox"
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_ROOT / "sandbox-targets" / "example-repo",
        target_adapter=adapter,
    )

    with pytest.raises(TargetAdapterError, match="missing_field"):
        runner.run(sandbox_run_id="SR-target-adapter-blocked")

    assert not (sandbox / "workspaces" / "SR-target-adapter-blocked").exists()
