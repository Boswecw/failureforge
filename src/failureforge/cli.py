"""CLI entrypoints invoked by the shell scripts under ``scripts/``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from failureforge.forgecommand import (
    OperatorClient,
    render_morning_report_text,
    render_receipt_detail_text,
    render_run_detail_text,
)
from failureforge.runtime.replay import replay_receipt
from failureforge.runtime.sandbox import CanonicalSourceMutationError, SandboxRunner
from failureforge.runtime.target_adapter import load_target_adapter
from failureforge.reporting.scorer import (
    build_hardening_report,
    load_and_verify_receipts,
    write_hardening_artifacts,
)
from failureforge.validation import (
    SchemaValidationError,
    ReceiptHashMismatch,
    validate_failure_receipt,
    verify_receipt_hash,
)


def _failureforge_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_run_target(
    *,
    root: Path,
    target: str,
    target_source_arg: str | None,
    adapter_arg: str | None,
) -> tuple[Path, dict | None]:
    if target_source_arg is not None and adapter_arg is None:
        raise ValueError("--target-source requires --adapter")

    if target_source_arg is None:
        target_source = root / "sandbox-targets" / target
    else:
        target_source = Path(target_source_arg)
        if not target_source.is_absolute():
            target_source = root / target_source

    adapter = None
    if adapter_arg is not None:
        adapter_path = Path(adapter_arg)
        if not adapter_path.is_absolute():
            adapter_path = root / adapter_path
        adapter = load_target_adapter(adapter_path)

    return target_source.resolve(), adapter


def cmd_run_sandbox(args: argparse.Namespace) -> int:
    root = _failureforge_root()
    sandbox_root = root / "sandbox"
    try:
        target_source, adapter = _load_run_target(
            root=root,
            target=args.target,
            target_source_arg=args.target_source,
            adapter_arg=args.adapter,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    runner = SandboxRunner(
        sandbox_root=sandbox_root,
        target_repo_name=args.target,
        target_repo_source=target_source,
        source_ref=args.source_ref,
        target_adapter=adapter,
        replay_target_source_arg=args.target_source,
        replay_adapter_arg=args.adapter,
    )
    try:
        result = runner.run(sandbox_run_id=args.run_id)
    except CanonicalSourceMutationError as exc:
        print(str(exc), file=sys.stderr)
        return 5
    receipts = load_and_verify_receipts(sandbox_root / "receipts")
    report = build_hardening_report(
        sandbox_run_id=result["sandbox_run"]["sandbox_run_id"],
        target_repo=args.target,
        receipts=[r for r in receipts if r["sandbox_run_id"] == result["sandbox_run"]["sandbox_run_id"]],
    )
    json_path, md_path = write_hardening_artifacts(
        report=report, sandbox_root=sandbox_root
    )
    print(json.dumps({
        "sandbox_run_id": result["sandbox_run"]["sandbox_run_id"],
        "receipts": len(result["receipt_paths"]),
        "report_json": str(json_path.relative_to(root)),
        "report_md": str(md_path.relative_to(root)),
    }, indent=2))
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    root = _failureforge_root()
    sandbox_root = root / "sandbox"
    receipt_path = Path(args.receipt_path)
    if not receipt_path.is_absolute():
        receipt_path = root / receipt_path
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    try:
        target_source, adapter = _load_run_target(
            root=root,
            target=receipt["target_repo"],
            target_source_arg=args.target_source,
            adapter_arg=args.adapter,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    result = replay_receipt(
        receipt_path=receipt_path,
        sandbox_root=sandbox_root,
        target_repo_source=target_source,
        target_adapter=adapter,
    )
    print(json.dumps(result.__dict__, indent=2))
    return 0 if result.matches_original else 2


def cmd_verify(args: argparse.Namespace) -> int:
    root = _failureforge_root()
    receipts_dir = root / "sandbox" / "receipts"
    rc = 0
    failures: list[dict[str, str]] = []
    paths = sorted(receipts_dir.glob("FHR-*.json"))
    if not paths:
        print(f"no receipts found under {receipts_dir}", file=sys.stderr)
        return 1
    for p in paths:
        body = json.loads(p.read_text(encoding="utf-8"))
        try:
            validate_failure_receipt(body)
            verify_receipt_hash(body)
        except (SchemaValidationError, ReceiptHashMismatch) as exc:
            failures.append({"receipt": str(p.relative_to(root)), "error": str(exc)})
            rc = 2
    summary = {"checked": len(paths), "failures": failures}
    print(json.dumps(summary, indent=2))
    return rc


def _operator_client(args: argparse.Namespace) -> OperatorClient:
    return OperatorClient(http=httpx.Client(base_url=args.dataforge_url, timeout=5.0))


def cmd_morning_report(args: argparse.Namespace) -> int:
    op = _operator_client(args)
    try:
        view = op.morning_report(
            target_repo=args.target_repo,
            runs_limit=args.runs,
            top_findings_limit=args.findings,
        )
    except httpx.HTTPError as exc:
        print(f"transport error: {exc!r}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(view, indent=2))
    else:
        sys.stdout.write(render_morning_report_text(view))
    return 0


def cmd_view_run(args: argparse.Namespace) -> int:
    op = _operator_client(args)
    try:
        detail = op.get_run_detail(args.run_id)
    except httpx.HTTPStatusError as exc:
        print(f"http {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(detail, indent=2))
    else:
        sys.stdout.write(render_run_detail_text(detail))
    return 0


def cmd_view_receipt(args: argparse.Namespace) -> int:
    op = _operator_client(args)
    try:
        receipt = op.get_receipt_detail(args.receipt_id)
    except httpx.HTTPStatusError as exc:
        print(f"http {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(receipt, indent=2))
    else:
        sys.stdout.write(render_receipt_detail_text(receipt))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="failureforge")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run-sandbox", help="copy target, run edge-case agent, emit receipts + report")
    p_run.add_argument("--target", required=True)
    p_run.add_argument("--source-ref", default="local")
    p_run.add_argument("--run-id", default=None)
    p_run.add_argument("--adapter", default=None, help="TargetAdapter.v1 JSON path")
    p_run.add_argument(
        "--target-source",
        default=None,
        help="canonical target source path; requires --adapter",
    )
    p_run.set_defaults(func=cmd_run_sandbox)

    p_replay = sub.add_parser("replay", help="re-run an attack from a FailureHarvestReceipt")
    p_replay.add_argument("receipt_path")
    p_replay.add_argument(
        "--target-source",
        default=None,
        help="canonical target source path; requires --adapter",
    )
    p_replay.add_argument("--adapter", default=None, help="TargetAdapter.v1 JSON path")
    p_replay.set_defaults(func=cmd_replay)

    p_verify = sub.add_parser("verify-receipts", help="validate every receipt's schema + hash")
    p_verify.set_defaults(func=cmd_verify)

    p_morning = sub.add_parser("morning-report", help="operator morning view: recent runs + top findings")
    p_morning.add_argument("--dataforge-url", default="http://127.0.0.1:8005")
    p_morning.add_argument("--target-repo", default=None)
    p_morning.add_argument("--runs", type=int, default=10)
    p_morning.add_argument("--findings", type=int, default=10)
    p_morning.add_argument("--json", action="store_true")
    p_morning.set_defaults(func=cmd_morning_report)

    p_run_view = sub.add_parser("view-run", help="operator detail for one sandbox run")
    p_run_view.add_argument("run_id")
    p_run_view.add_argument("--dataforge-url", default="http://127.0.0.1:8005")
    p_run_view.add_argument("--json", action="store_true")
    p_run_view.set_defaults(func=cmd_view_run)

    p_receipt_view = sub.add_parser("view-receipt", help="operator detail for one receipt")
    p_receipt_view.add_argument("receipt_id")
    p_receipt_view.add_argument("--dataforge-url", default="http://127.0.0.1:8005")
    p_receipt_view.add_argument("--json", action="store_true")
    p_receipt_view.set_defaults(func=cmd_view_receipt)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
