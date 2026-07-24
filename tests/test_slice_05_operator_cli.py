"""Slice 05 — operator read-only morning-report CLI + client tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATAFORGE_LOCAL = _REPO_ROOT / "dataforge-Local"

# This slice exercises the FailureForge -> DataForge Local handshake, which lives
# in the sibling ``dataforge-Local`` repo and needs FastAPI. Skip cleanly when
# running this repo standalone (e.g. in its own CI) so collection stays green.
pytest.importorskip(
    "fastapi", reason="dataforge-Local integration test requires fastapi"
)
if not _DATAFORGE_LOCAL.exists():
    pytest.skip(
        "dataforge-Local sibling repo not present; cross-repo integration test",
        allow_module_level=True,
    )
if str(_DATAFORGE_LOCAL) not in sys.path:
    sys.path.insert(0, str(_DATAFORGE_LOCAL))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from failureforge.forgecommand import (  # noqa: E402
    OperatorClient,
    render_morning_report_text,
    render_receipt_detail_text,
    render_run_detail_text,
)
from failureforge.persistence import DataForgeFailureForgeClient  # noqa: E402
from failureforge.runtime.sandbox import SandboxRunner  # noqa: E402

_FF_ROOT = Path(__file__).resolve().parents[1]


def _make_app() -> FastAPI:
    from app.failureforge.router import router as failureforge_router
    from app.failureforge.service import FailureForgeService

    fa = FastAPI()
    fa.include_router(failureforge_router)
    fa.state.failureforge_service = FailureForgeService()
    return fa


def _seed_one_run(http: TestClient, tmp_path: Path) -> str:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner = SandboxRunner(
        sandbox_root=sandbox,
        target_repo_name="example-repo",
        target_repo_source=_FF_ROOT / "sandbox-targets" / "example-repo",
    )
    runner.run(sandbox_run_id="SR-op-cli")

    from failureforge.reporting.scorer import (
        build_hardening_report,
        load_and_verify_receipts,
        write_hardening_artifacts,
    )

    receipts = load_and_verify_receipts(sandbox / "receipts")
    report = build_hardening_report(
        sandbox_run_id="SR-op-cli", target_repo="example-repo", receipts=receipts
    )
    write_hardening_artifacts(report=report, sandbox_root=sandbox)

    push = DataForgeFailureForgeClient(http_client=http)
    summary = push.push_run_bundle_from_disk(run_id="SR-op-cli", sandbox_root=sandbox)
    assert summary.all_accepted
    return "SR-op-cli"


@pytest.fixture
def app() -> FastAPI:
    return _make_app()


@pytest.fixture
def http(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---- client + renderer round trips -----------------------------------


def test_operator_client_morning_report_includes_top_finding(
    tmp_path: Path, http: TestClient
):
    _seed_one_run(http, tmp_path)
    op = OperatorClient(http=http)
    view = op.morning_report()
    assert view["summary"]["runs_total"] >= 1
    assert view["summary"]["ready_for_gate_total"] >= 1
    assert view["top_findings"][0]["severity"] == "high"
    text = render_morning_report_text(view)
    assert "FailureForge — Morning Report" in text
    assert "Recent runs:" in text
    assert "Top findings ready for gate:" in text


def test_operator_client_run_detail_renders(tmp_path: Path, http: TestClient):
    _seed_one_run(http, tmp_path)
    op = OperatorClient(http=http)
    detail = op.get_run_detail("SR-op-cli")
    text = render_run_detail_text(detail)
    assert "Sandbox run SR-op-cli" in text
    assert "Receipts:" in text


def test_operator_client_receipt_detail_includes_copy_paste_replay(
    tmp_path: Path, http: TestClient
):
    _seed_one_run(http, tmp_path)
    op = OperatorClient(http=http)
    runs = op.list_runs()
    assert runs
    detail = op.get_run_detail(runs[0]["sandbox_run_id"])
    receipt_id = detail["receipts"][0]["receipt_id"]
    receipt = op.get_receipt_detail(receipt_id)
    text = render_receipt_detail_text(receipt)
    assert "Replay command (copy/paste):" in text
    assert receipt["repro_command"] in text


# ---- CLI surface -----------------------------------------------------


def test_cli_morning_report_subcommand(
    tmp_path: Path, http: TestClient, monkeypatch, capsys
):
    _seed_one_run(http, tmp_path)

    # Patch the CLI's OperatorClient creator to use our TestClient.
    from failureforge import cli as cli_mod

    def _fake_op_client(args):
        return OperatorClient(http=http)

    monkeypatch.setattr(cli_mod, "_operator_client", _fake_op_client)

    rc = cli_mod.main(["morning-report", "--target-repo", "example-repo"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Top findings ready for gate" in captured.out
    assert "Replay:" in captured.out


def test_cli_view_run_and_view_receipt(
    tmp_path: Path, http: TestClient, monkeypatch, capsys
):
    _seed_one_run(http, tmp_path)
    from failureforge import cli as cli_mod

    def _fake_op_client(args):
        return OperatorClient(http=http)

    monkeypatch.setattr(cli_mod, "_operator_client", _fake_op_client)

    rc = cli_mod.main(["view-run", "SR-op-cli"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Sandbox run SR-op-cli" in out

    op = OperatorClient(http=http)
    receipt_id = op.get_run_detail("SR-op-cli")["receipts"][0]["receipt_id"]
    rc = cli_mod.main(["view-receipt", receipt_id, "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    body = json.loads(out)
    assert body["receipt_id"] == receipt_id
    assert body["repro_command"].endswith(".json")
