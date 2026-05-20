"""Slice 03 — Hardening report ranking.

Scoring formula (per plan §07):

    score =
        severity_weight
      + reproducibility_weight
      + blast_radius_weight
      + frequency_weight
      - fix_complexity_penalty
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from failureforge.validation import (
    validate_failure_receipt,
    validate_hardening_report,
    verify_receipt_hash,
)

_SEVERITY_WEIGHT = {
    "critical": 100,
    "high": 60,
    "medium": 30,
    "low": 10,
    "info": 0,
}
_REPRO_WEIGHT = {
    "reproducible": 30,
    "intermittent": 10,
    "non_reproducible": 0,
}
_BLAST_WEIGHT = {
    "ecosystem": 25,
    "subsystem": 15,
    "service": 10,
    "repo": 5,
    "unknown": 2,
}
_FIX_PENALTY = {
    "trivial": 0,
    "small": 5,
    "medium": 15,
    "large": 30,
    "unknown": 10,
}


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _stable_id(prefix: str, *parts: str) -> str:
    import hashlib

    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def _classify_blast_radius(receipt: dict[str, Any]) -> str:
    classification = receipt.get("classification", "")
    if classification in ("state_failure",):
        return "subsystem"
    if classification in ("duplicate_replay", "missing_field", "unknown_enum"):
        return "service"
    if classification in ("bad_path", "bad_unicode", "malformed_input"):
        return "repo"
    return "unknown"


def _classify_fix_complexity(receipt: dict[str, Any]) -> str:
    classification = receipt.get("classification", "")
    return {
        "duplicate_replay": "small",
        "missing_field": "small",
        "unknown_enum": "small",
        "bad_path": "medium",
        "bad_unicode": "medium",
        "malformed_input": "small",
        "state_failure": "medium",
        "boundary": "medium",
        "no_failure_observed": "trivial",
    }.get(classification, "unknown")


def _classify_reproducibility(receipt: dict[str, Any]) -> str:
    if not receipt.get("reproducible", False):
        return "non_reproducible"
    return "reproducible"


def _recommended_fix(receipt: dict[str, Any]) -> str:
    return {
        "duplicate_replay": "enforce idempotency on the request key (existing-result reuse).",
        "missing_field": "validate required fields at the registry boundary; reject with a typed error.",
        "unknown_enum": "validate enums at the boundary against the canonical set.",
        "bad_path": "reject paths containing `..` or absolute escapes; canonicalize before write.",
        "bad_unicode": "strip or reject control characters; assert NFC after normalisation.",
        "malformed_input": "type-check input shape at the boundary; raise a typed error.",
        "state_failure": "investigate the divergence: actual_result must match invariant.",
        "no_failure_observed": "no fix needed; case may be promoted into the regression gate.",
    }.get(receipt.get("classification", ""), "investigate; case requires manual triage.")


def _ready_for_gate(receipt: dict[str, Any]) -> bool:
    """A failure is ready to become a regression gate only when:
    - it is reproducible, AND
    - it is a real failure (not no_failure_observed)."""
    return bool(receipt.get("reproducible")) and receipt.get("classification") != "no_failure_observed"


def _logical_attack_id(receipt: dict[str, Any]) -> str:
    """Strip lane prefixes (FC-REPRO-, FC-CLASS-, FC-MUTATION-, FC-CHAOS-) so
    that lane-distinct receipts that target the same canonical attack cluster
    into one finding for cross-agent agreement."""
    fid: str = receipt["failure_case_id"]
    for prefix in ("FC-REPRO-", "FC-CLASS-", "FC-MUTATION-", "FC-CHAOS-"):
        if fid.startswith(prefix):
            return fid[len(prefix) :] if fid[len(prefix) :].startswith("FC-") else fid
    return fid


def score_findings(receipts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group equivalent receipts and produce ranked-finding dicts.

    Equivalent receipts are grouped by ``(target_repo, classification,
    logical_attack_id)`` so receipts emitted by different agent lanes that
    target the same canonical attack cluster into a single finding. The
    distinct ``agent_lane`` set inside the group is the cross-agent
    agreement signal — Slice 07 boosts the score by
    ``(lane_agreement - 1) * 12`` so agreed-upon findings outrank
    single-lane signals at equal severity.
    """
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in receipts:
        key = (r["target_repo"], r["classification"], _logical_attack_id(r))
        groups[key].append(r)

    findings: list[dict[str, Any]] = []
    for (_repo, _cls, _case), group in groups.items():
        # Pick the worst severity in the group.
        worst = max(group, key=lambda x: _SEVERITY_WEIGHT.get(x.get("severity", "info"), 0))
        repro = "reproducible" if any(x.get("reproducible") for x in group) else "non_reproducible"
        blast = _classify_blast_radius(worst)
        fix_complexity = _classify_fix_complexity(worst)
        lanes = sorted({r.get("agent_lane") for r in group if r.get("agent_lane")})
        if not lanes:
            lanes = ["edge_case"]
        lane_agreement = len(lanes)
        agreement_boost = (lane_agreement - 1) * 12  # Slice 07 cross-agent boost
        score = (
            _SEVERITY_WEIGHT.get(worst.get("severity", "info"), 0)
            + _REPRO_WEIGHT.get(repro, 0)
            + _BLAST_WEIGHT.get(blast, 0)
            + len(group)  # frequency_weight: 1 point per recurrence
            + agreement_boost
            - _FIX_PENALTY.get(fix_complexity, 10)
        )
        findings.append(
            {
                "rank": 0,  # set after sort
                "failure_id": worst["failure_case_id"],
                "classification": worst["classification"],
                "severity": worst.get("severity", "info"),
                "reproducibility": repro,
                "blast_radius": blast,
                "frequency": len(group),
                "fix_complexity": fix_complexity,
                "score": score,
                "recommended_fix": _recommended_fix(worst),
                "receipts": [r["receipt_id"] for r in group],
                "repro_command": worst.get("repro_command", ""),
                "ready_for_gate": _ready_for_gate(worst),
                "lanes": lanes,
                "lane_agreement": lane_agreement,
            }
        )

    findings.sort(
        key=lambda f: (
            -f["score"],
            -_SEVERITY_WEIGHT.get(f["severity"], 0),
            f["failure_id"],
        )
    )
    for i, f in enumerate(findings, start=1):
        f["rank"] = i
    return findings


def build_hardening_report(
    *,
    sandbox_run_id: str,
    target_repo: str,
    receipts: Iterable[dict[str, Any]],
    report_id: str | None = None,
) -> dict[str, Any]:
    """Build a HardeningReport.v1 dict, validate it, and return it.

    Receipts must already pass schema validation and hash verification
    (callers are expected to feed verified receipts in)."""
    receipts_list = list(receipts)
    findings = score_findings(receipts_list)
    reproducible_total = sum(1 for r in receipts_list if r.get("reproducible"))
    summary = (
        f"{len(receipts_list)} receipts produced, {reproducible_total} reproducible, "
        f"top finding: {findings[0]['recommended_fix'] if findings else 'no findings'}"
    )
    rid = report_id or _stable_id("HR", sandbox_run_id, target_repo)
    report = {
        "schema_version": "HardeningReport.v1",
        "report_id": rid,
        "sandbox_run_id": sandbox_run_id,
        "target_repo": target_repo,
        "summary": summary,
        "ranked_findings": findings,
        "created_at": _utc_now(),
        "receipts_total": len(receipts_list),
        "reproducible_total": reproducible_total,
    }
    validate_hardening_report(report)
    return report


def render_hardening_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hardening Report",
        "",
        "## Summary",
        "",
        f"- Target repo: `{report['target_repo']}`",
        f"- Sandbox run: `{report['sandbox_run_id']}`",
        f"- Receipts produced: {report.get('receipts_total', len(report['ranked_findings']))}",
        f"- Reproducible failures: {report.get('reproducible_total', '?')}",
    ]
    if report["ranked_findings"]:
        top = report["ranked_findings"][0]
        lines.append(f"- Top recommended fix: {top['recommended_fix']}")
    lines.extend(["", "## Ranked Findings", ""])
    for f in report["ranked_findings"]:
        lines.append(
            f"{f['rank']}. [{f['severity'].upper()}] {f['classification']} (score={f['score']})"
        )
        lines.append(f"   - Failure case: `{f['failure_id']}`")
        lines.append(f"   - Reproducibility: {f['reproducibility']}")
        lines.append(f"   - Blast radius: {f['blast_radius']}")
        lines.append(f"   - Frequency: {f['frequency']}")
        lines.append(f"   - Fix complexity: {f['fix_complexity']}")
        lines.append(f"   - Recommended fix: {f['recommended_fix']}")
        lines.append(f"   - Repro command: `{f['repro_command']}`")
        lines.append(f"   - Receipts: {', '.join(f['receipts'])}")
        if f.get("lanes"):
            lines.append(
                f"   - Cross-agent agreement: {f.get('lane_agreement', len(f['lanes']))} lane(s) "
                f"({', '.join(f['lanes'])})"
            )
        lines.append(f"   - Ready for gate: {'yes' if f['ready_for_gate'] else 'no'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_hardening_artifacts(
    *,
    report: dict[str, Any],
    sandbox_root: Path,
) -> tuple[Path, Path]:
    reports_dir = sandbox_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"{report['report_id']}.json"
    md_path = reports_dir / f"{report['report_id']}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_hardening_markdown(report), encoding="utf-8")
    return json_path, md_path


def load_and_verify_receipts(receipts_dir: Path) -> list[dict[str, Any]]:
    """Load every FHR-*.json under ``receipts_dir``, validate the schema, and
    verify the receipt hash. Receipts that fail either check are rejected
    with a raised exception — callers must NOT silently drop them."""
    receipts: list[dict[str, Any]] = []
    for path in sorted(receipts_dir.glob("FHR-*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        validate_failure_receipt(body)
        verify_receipt_hash(body)
        receipts.append(body)
    return receipts
