"""Toy registry used as the FailureForge example target.

Has a deliberate idempotency bug: every ``upsert`` creates a new record even
for inputs that should be deduplicated by their `key`. The Edge-Case Agent's
``duplicate_replay`` attack exposes this bug.
"""

from __future__ import annotations

import os
from typing import Any


_ALLOWED_KINDS = {"asset", "config", "policy"}


class Registry:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def upsert(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a mapping")
        if "key" not in payload:
            raise KeyError("missing required field: key")
        if "value" not in payload:
            raise KeyError("missing required field: value")
        if "kind" in payload and payload["kind"] not in _ALLOWED_KINDS:
            raise ValueError(f"unknown kind: {payload['kind']}")
        if "path" in payload:
            path = str(payload["path"])
            if ".." in path or path.startswith("/"):
                raise ValueError(f"unsafe path: {path}")
            if "\x00" in path:
                raise ValueError("path contains NUL")
        # NOTE: deliberate bug — no dedupe on `key`. Each call creates a new id.
        self._counter += 1
        new_id = f"r{self._counter:04d}"
        self._records[new_id] = dict(payload)
        return new_id

    def size(self) -> int:
        return len(self._records)

    def dump(self) -> dict[str, Any]:
        return {rid: dict(rec) for rid, rec in self._records.items()}
