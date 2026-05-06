"""Base protocol for FailureForge agent lanes.

Each agent implements:

- ``lane``: one of the ``agent_lane`` enum values from ``FailureCase.v1``.
- ``produce(workspace, target_repo)``: returns a list of ``AttackOutcome``
  records that the sandbox runner will turn into FailureHarvestReceipts.

Agents are sandbox-only: they read the copied workspace and may invoke
target code, but they MUST NOT mutate the canonical repo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from failureforge.runtime.sandbox import AttackOutcome


class Agent(Protocol):
    lane: str

    def produce(self, *, workspace: Path, target_repo: str) -> list[AttackOutcome]: ...
