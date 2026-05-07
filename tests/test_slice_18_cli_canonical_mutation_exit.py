"""Slice 18 CLI canonical-mutation exit tests."""

from __future__ import annotations

from typing import Any

from failureforge.cli import main
from failureforge.runtime import CanonicalSourceMutationError


class _RaisingRunner:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def run(self, *, sandbox_run_id: str | None = None) -> dict[str, Any]:
        raise CanonicalSourceMutationError(
            {
                "canonical_source_hash_before": "0" * 64,
                "canonical_source_hash_after": "1" * 64,
            }
        )


def test_run_sandbox_cli_returns_5_for_canonical_mutation(monkeypatch, capsys):
    import failureforge.cli as cli

    monkeypatch.setattr(cli, "SandboxRunner", _RaisingRunner)

    rc = main(["run-sandbox", "--target", "example-repo", "--run-id", "SR-s18"])

    captured = capsys.readouterr()
    assert rc == 5
    assert "canonical source mutated during sandbox run" in captured.err
    assert "Traceback" not in captured.err
