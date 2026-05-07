"""Slice 13 target-adapter preflight enforcement tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from failureforge.runtime import (
    SandboxRunner,
    TargetAdapterError,
    validate_target_adapter_for_source,
)


_ROOT = Path(__file__).resolve().parents[1]


def _valid_adapter() -> dict:
    return json.loads(
        (_ROOT / "fixtures/valid/TargetAdapter.v1.valid.json").read_text(
            encoding="utf-8"
        )
    )


def test_adapter_preflight_rejects_missing_required_command(tmp_path: Path):
    adapter = _valid_adapter()
    adapter["required_commands"] = ["ff-command-that-should-not-exist-13"]

    with pytest.raises(TargetAdapterError, match="required command"):
        validate_target_adapter_for_source(
            adapter,
            target_repo_source=_ROOT / "sandbox-targets" / "example-repo",
            sandbox_root=tmp_path / "sandbox",
        )


def test_adapter_preflight_rejects_forbidden_source_path(tmp_path: Path):
    source = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", source)
    source.joinpath(".env").write_text("SECRET=do-not-copy\n", encoding="utf-8")

    with pytest.raises(TargetAdapterError, match="forbidden path exists"):
        validate_target_adapter_for_source(
            _valid_adapter(),
            target_repo_source=source,
            sandbox_root=tmp_path / "sandbox",
        )


def test_sandbox_runner_rejects_forbidden_path_before_workspace_copy(tmp_path: Path):
    source = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", source)
    source.joinpath(".env").write_text("SECRET=do-not-copy\n", encoding="utf-8")
    sandbox = tmp_path / "sandbox"

    with pytest.raises(TargetAdapterError, match="forbidden path exists"):
        SandboxRunner(
            sandbox_root=sandbox,
            target_repo_name="example-repo",
            target_repo_source=source,
            target_adapter=_valid_adapter(),
        )

    assert not sandbox.exists()
