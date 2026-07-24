"""Slice 15 replay command context tests."""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

from failureforge.runtime import SandboxRunner, load_target_adapter

_ROOT = Path(__file__).resolve().parents[1]


def _adapter() -> dict:
    return load_target_adapter(_ROOT / "fixtures/valid/TargetAdapter.v1.valid.json")


def _duplicate_receipt(paths: list[str]) -> dict:
    for raw_path in paths:
        body = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        if body["classification"] == "duplicate_replay":
            return body
    raise AssertionError("duplicate_replay receipt not found")


def test_default_run_repro_command_stays_legacy(tmp_path: Path):
    runner = SandboxRunner(
        sandbox_root=tmp_path / "sandbox",
        target_repo_name="example-repo",
        target_repo_source=_ROOT / "sandbox-targets" / "example-repo",
    )

    result = runner.run(sandbox_run_id="SR-s15-default")
    receipt = _duplicate_receipt(result["receipt_paths"])

    assert shlex.split(receipt["repro_command"]) == [
        "./scripts/replay_failure.sh",
        f"sandbox/receipts/{receipt['receipt_id']}.json",
    ]


def test_adapter_external_run_repro_command_carries_replay_context(tmp_path: Path):
    external = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", external)
    adapter_arg = "fixtures/valid/TargetAdapter.v1.valid.json"
    runner = SandboxRunner(
        sandbox_root=tmp_path / "sandbox",
        target_repo_name="example-repo",
        target_repo_source=external,
        target_adapter=_adapter(),
        replay_target_source_arg=str(external),
        replay_adapter_arg=adapter_arg,
    )

    result = runner.run(sandbox_run_id="SR-s15-external")
    receipt = _duplicate_receipt(result["receipt_paths"])

    assert shlex.split(receipt["repro_command"]) == [
        "./scripts/replay_failure.sh",
        f"sandbox/receipts/{receipt['receipt_id']}.json",
        "--target-source",
        str(external),
        "--adapter",
        adapter_arg,
    ]
