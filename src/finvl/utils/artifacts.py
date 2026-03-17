"""
Experiment artifact management for FinVL-MAS.
Saves decision traces, chart annotations, and config snapshots.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class ArtifactManager:
    """Manages experiment artifacts: configs, decisions, charts, traces."""

    def __init__(self, base_dir: str = "outputs/artifacts"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_decision(
        self,
        date: str,
        decision: Dict[str, Any],
        trace: str = "",
        memory: Dict[str, Any] | None = None,
    ) -> str:
        """Save a single decision artifact."""
        artifact = {
            "date": date,
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "reasoning_trace": trace,
        }
        if memory:
            safe_mem = {}
            for k, v in memory.items():
                try:
                    json.dumps(v)
                    safe_mem[k] = v
                except (TypeError, ValueError):
                    safe_mem[k] = str(v)
            artifact["memory_snapshot"] = safe_mem

        path = self.base_dir / f"decision_{date}.json"
        with open(path, "w") as f:
            json.dump(artifact, f, indent=2, default=str)
        return str(path)

    def save_config_snapshot(self, config: Dict[str, Any], label: str = "config") -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.base_dir / f"{label}_{ts}.json"
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
        return str(path)
