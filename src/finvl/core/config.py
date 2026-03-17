"""
Configuration loading for FinVL-MAS.
Loads YAML configs and provides typed access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def load_config(config_path: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load a YAML config file with optional overrides."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(path) as f:
        cfg = yaml.safe_load(f)

    if overrides:
        _deep_update(cfg, overrides)
    return cfg


def _deep_update(base: dict, update: dict) -> dict:
    """Recursively update nested dicts."""
    for k, v in update.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def merge_ablation_config(
    base_path: str,
    ablation_path: str,
) -> Dict[str, Any]:
    """Load base config and overlay ablation overrides."""
    base = load_config(base_path)
    ablation = load_config(ablation_path)
    return _deep_update(base, ablation)
