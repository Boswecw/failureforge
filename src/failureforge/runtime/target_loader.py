"""Load the example target's registry module from a copied workspace."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def load_registry_module(workspace_path: Path) -> types.ModuleType:
    """Load `registry.py` from the copied workspace under a private module name.

    The same workspace can be loaded multiple times; we cache by absolute path
    in ``sys.modules`` so attacks see consistent state per workspace.
    """
    target = workspace_path / "registry.py"
    if not target.exists():
        raise FileNotFoundError(f"target workspace has no registry.py: {target}")
    mod_name = f"_ff_target_{abs(hash(str(target.resolve())))}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, target)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {target}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module
