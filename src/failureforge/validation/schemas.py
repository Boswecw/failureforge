"""JSON Schema validators for the four FailureForge contracts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

_SCHEMA_ROOT = Path(__file__).resolve().parents[3] / "schemas"


class SchemaValidationError(Exception):
    """Raised when a record fails contract validation."""

    def __init__(
        self, schema_name: str, message: str, *, field_path: str | None = None
    ):
        super().__init__(f"{schema_name}: {message}")
        self.schema_name = schema_name
        self.message = message
        self.field_path = field_path


@lru_cache(maxsize=16)
def _load(name: str) -> dict[str, Any]:
    path = _SCHEMA_ROOT / name
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _path(path) -> str:  # noqa: ANN001
    if not path:
        return ""
    return "/" + "/".join(str(p) for p in path)


@lru_cache(maxsize=1)
def _schema_registry() -> Registry:
    """Build a ``referencing`` Registry of every sibling schema, keyed by its
    bare filename so cross-file ``{"$ref": "Other.v1.schema.json"}`` links
    resolve. Replaces the deprecated ``jsonschema.RefResolver``."""
    resources = []
    for path in sorted(_SCHEMA_ROOT.glob("*.schema.json")):
        resource = Resource.from_contents(
            _load(path.name), default_specification=DRAFT7
        )
        resources.append((path.name, resource))
    return Registry().with_resources(resources)


def _validate(schema_name: str, doc: Any) -> None:
    schema = _load(schema_name)
    validator = Draft7Validator(schema, registry=_schema_registry())
    try:
        validator.validate(doc)
    except _JSValidationError as exc:
        raise SchemaValidationError(
            schema_name, exc.message, field_path=_path(list(exc.absolute_path))
        ) from exc


def validate_failure_case(doc: dict[str, Any]) -> None:
    _validate("FailureCase.v1.schema.json", doc)


def validate_failure_receipt(doc: dict[str, Any]) -> None:
    _validate("FailureHarvestReceipt.v1.schema.json", doc)


def validate_sandbox_run(doc: dict[str, Any]) -> None:
    _validate("SandboxRun.v1.schema.json", doc)


def validate_hardening_report(doc: dict[str, Any]) -> None:
    _validate("HardeningReport.v1.schema.json", doc)


def validate_approval_receipt(doc: dict[str, Any]) -> None:
    _validate("ApprovalReceipt.v1.schema.json", doc)


def validate_promotion_candidate(doc: dict[str, Any]) -> None:
    _validate("PromotionCandidate.v1.schema.json", doc)


def validate_root_cause_cluster(doc: dict[str, Any]) -> None:
    _validate("RootCauseCluster.v1.schema.json", doc)


def validate_fix_cluster_report(doc: dict[str, Any]) -> None:
    _validate("FixClusterReport.v1.schema.json", doc)


def validate_model_adjudication_receipt(doc: dict[str, Any]) -> None:
    _validate("ModelAdjudicationReceipt.v1.schema.json", doc)


def validate_neuroforge_adjudication_report(doc: dict[str, Any]) -> None:
    _validate("NeuroForgeAdjudicationReport.v1.schema.json", doc)


def validate_failure_score_v2(doc: dict[str, Any]) -> None:
    _validate("FailureScore.v2.schema.json", doc)


def validate_failureforge_to_era_export(doc: dict[str, Any]) -> None:
    _validate("FailureForgeToERAExport.v1.schema.json", doc)


def validate_failureforge_aar_seed(doc: dict[str, Any]) -> None:
    _validate("FailureForgeAARSeed.v1.schema.json", doc)


def validate_target_adapter(doc: dict[str, Any]) -> None:
    _validate("TargetAdapter.v1.schema.json", doc)
