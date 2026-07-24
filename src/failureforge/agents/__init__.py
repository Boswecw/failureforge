"""Agent lane exports.

The concrete agent modules intentionally import runtime types, and the runtime
imports the edge-case agent. Keep package-level exports lazy so CLI startup can
import ``failureforge.runtime.sandbox`` without a package import cycle.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ChaosAgent",
    "ClassificationAgent",
    "EdgeCaseAgent",
    "MutationAgent",
    "ReproductionAgent",
]


def __getattr__(name: str) -> Any:
    if name == "ChaosAgent":
        from failureforge.agents.chaos import ChaosAgent

        return ChaosAgent
    if name == "ClassificationAgent":
        from failureforge.agents.classification import ClassificationAgent

        return ClassificationAgent
    if name == "EdgeCaseAgent":
        from failureforge.agents.edge_case import EdgeCaseAgent

        return EdgeCaseAgent
    if name == "MutationAgent":
        from failureforge.agents.mutation import MutationAgent

        return MutationAgent
    if name == "ReproductionAgent":
        from failureforge.agents.reproduction import ReproductionAgent

        return ReproductionAgent
    raise AttributeError(name)
