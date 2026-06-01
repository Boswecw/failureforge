"""Load the example target's registry module from a copied workspace."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import types
from pathlib import Path


def load_registry_module(workspace_path: Path) -> types.ModuleType:
    """Load `registry.py` from the copied workspace under a private module name.

    The module name is a deterministic SHA-256 of the resolved path *and* the
    file's current contents. This is stable across processes (unlike the salted
    builtin ``hash``) and collision-resistant. Folding in the contents also means
    a workspace that is re-copied with different code gets a fresh module instead
    of a stale cached one, while identical re-copies reuse the cache so repeated
    attacks against one workspace see a consistent module.
    """
    target = workspace_path / "registry.py"
    if not target.exists():
        raise FileNotFoundError(f"target workspace has no registry.py: {target}")
    fingerprint = hashlib.sha256()
    fingerprint.update(str(target.resolve()).encode("utf-8"))
    fingerprint.update(b"\0")
    fingerprint.update(target.read_bytes())
    mod_name = f"_ff_target_{fingerprint.hexdigest()[:16]}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, target)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {target}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module
