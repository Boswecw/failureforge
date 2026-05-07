"""TargetAdapter.v1 runtime guard.

Adapters do not make FailureForge more permissive. They document and enforce
the minimum safety posture required before a non-demo target is probed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from failureforge.validation import validate_target_adapter


class TargetAdapterError(ValueError):
    """Raised when a target adapter would weaken sandbox safety."""


def load_target_adapter(path: Path) -> dict[str, Any]:
    """Load and schema-validate a TargetAdapter.v1 JSON file."""
    adapter = json.loads(path.read_text(encoding="utf-8"))
    validate_target_adapter(adapter)
    return adapter


def validate_target_adapter_for_source(
    adapter: dict[str, Any],
    *,
    target_repo_source: Path,
    sandbox_root: Path,
) -> dict[str, Any]:
    """Verify adapter safety against the selected canonical target source."""
    validate_target_adapter(adapter)
    source = target_repo_source.resolve()
    sandbox = sandbox_root.resolve()

    if adapter["target_repo"] != source.name:
        raise TargetAdapterError(
            "adapter target_repo does not match target source directory: "
            f"{adapter['target_repo']!r} != {source.name!r}"
        )

    try:
        source.relative_to(sandbox)
    except ValueError:
        pass
    else:
        raise TargetAdapterError(
            "adapter target source must be outside the sandbox tree"
        )

    guard = adapter["canonical_mutation_guard"]
    if guard["enabled"] is not True or guard["strategy"] != "pre_post_tree_hash":
        raise TargetAdapterError("adapter must require pre/post canonical hashing")

    for raw_path in adapter["forbidden_paths"]:
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts:
            raise TargetAdapterError(
                f"adapter forbidden path must be relative and contained: {raw_path!r}"
            )

    allowed_roots = set(adapter["artifact_capture_rules"]["allowed_roots"])
    if not allowed_roots.issubset(
        {"sandbox/runs", "sandbox/receipts", "sandbox/reports", "sandbox/exports"}
    ):
        raise TargetAdapterError("adapter artifact roots must stay under sandbox/")

    return adapter


def ensure_attack_family_supported(adapter: dict[str, Any], attack_type: str) -> None:
    if attack_type not in set(adapter["supported_attack_families"]):
        raise TargetAdapterError(
            f"adapter {adapter['adapter_id']} does not allow attack family {attack_type!r}"
        )
