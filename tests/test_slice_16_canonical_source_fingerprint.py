"""Slice 16 canonical-source fingerprint tests."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from failureforge.runtime import SandboxRunner, load_target_adapter
from failureforge.validation import validate_sandbox_run


_ROOT = Path(__file__).resolve().parents[1]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _adapter() -> dict:
    return load_target_adapter(_ROOT / "fixtures/valid/TargetAdapter.v1.valid.json")


def test_sandbox_run_records_canonical_source_hashes(tmp_path: Path):
    runner = SandboxRunner(
        sandbox_root=tmp_path / "sandbox",
        target_repo_name="example-repo",
        target_repo_source=_ROOT / "sandbox-targets" / "example-repo",
    )

    result = runner.run(sandbox_run_id="SR-s16-fingerprint")
    sandbox_run = result["sandbox_run"]

    validate_sandbox_run(sandbox_run)
    assert _SHA256.match(sandbox_run["canonical_source_hash_before"])
    assert _SHA256.match(sandbox_run["canonical_source_hash_after"])
    assert sandbox_run["canonical_source_hash_before"] == sandbox_run[
        "canonical_source_hash_after"
    ]
    assert sandbox_run["canonical_source_mutated"] is False


def test_external_adapter_run_records_source_hashes(tmp_path: Path):
    external = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", external)
    runner = SandboxRunner(
        sandbox_root=tmp_path / "sandbox",
        target_repo_name="example-repo",
        target_repo_source=external,
        target_adapter=_adapter(),
    )

    result = runner.run(sandbox_run_id="SR-s16-external-fingerprint")
    sandbox_run = result["sandbox_run"]

    validate_sandbox_run(sandbox_run)
    assert sandbox_run["canonical_source_hash_before"] == sandbox_run[
        "canonical_source_hash_after"
    ]
    assert sandbox_run["canonical_source_mutated"] is False
