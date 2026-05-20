"""Slice 12 external target-source gating tests."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pytest

from failureforge.cli import _load_run_target, main

_ROOT = Path(__file__).resolve().parents[1]


def _namespace(**overrides):
    base = {
        "target": "example-repo",
        "target_source": None,
        "adapter": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_default_target_source_stays_on_demo_sandbox_target():
    args = _namespace()

    source, adapter = _load_run_target(
        root=_ROOT,
        target=args.target,
        target_source_arg=args.target_source,
        adapter_arg=args.adapter,
    )

    assert source == (_ROOT / "sandbox-targets" / "example-repo").resolve()
    assert adapter is None


def test_external_target_source_requires_adapter(tmp_path: Path):
    external = tmp_path / "example-repo"
    external.mkdir()

    with pytest.raises(ValueError, match="requires --adapter"):
        _load_run_target(
            root=_ROOT,
            target="example-repo",
            target_source_arg=str(external),
            adapter_arg=None,
        )


def test_external_target_source_with_adapter_resolves_absolute_path(tmp_path: Path):
    external = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", external)

    source, adapter = _load_run_target(
        root=_ROOT,
        target="example-repo",
        target_source_arg=str(external),
        adapter_arg="fixtures/valid/TargetAdapter.v1.valid.json",
    )

    assert source == external.resolve()
    assert adapter is not None
    assert adapter["target_repo"] == "example-repo"


def test_cli_rejects_external_target_source_without_adapter(tmp_path: Path, capsys):
    external = tmp_path / "example-repo"
    external.mkdir()

    rc = main(
        [
            "run-sandbox",
            "--target",
            "example-repo",
            "--target-source",
            str(external),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "--target-source requires --adapter" in captured.err


def test_cli_runs_external_target_source_with_adapter(tmp_path: Path, capsys):
    external = tmp_path / "example-repo"
    shutil.copytree(_ROOT / "sandbox-targets" / "example-repo", external)

    rc = main(
        [
            "run-sandbox",
            "--target",
            "example-repo",
            "--target-source",
            str(external),
            "--adapter",
            "fixtures/valid/TargetAdapter.v1.valid.json",
            "--run-id",
            "SR-external-source",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert rc == 0
    assert payload["sandbox_run_id"] == "SR-external-source"
    assert payload["receipts"] > 0
