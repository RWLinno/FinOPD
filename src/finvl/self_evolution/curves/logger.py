"""
Evolution Curve Logger: records per-iteration metrics for monitoring
self-evolution progress and generating Figure 4.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class EvolutionLogger:
    """
    Logs iteration-level metrics during self-evolution:
    - val_sharpe, val_alpha_decay
    - belief_size, belief_hit_rate
    - router_entropy
    - kl_divergence
    """

    def __init__(self):
        self._records: List[Dict[str, Any]] = []

    def log_iteration(self, metrics: Dict[str, Any]):
        """Log metrics for one iteration."""
        self._records.append(metrics)
        logger.info(f"Evolution iter {len(self._records)}: {metrics}")

    def save(self, path: str):
        """Save evolution curve to JSONL."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for record in self._records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(f"Evolution curve saved: {len(self._records)} records -> {path}")

    def load(self, path: str):
        """Load evolution curve from JSONL."""
        p = Path(path)
        if not p.exists():
            return
        self._records = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                self._records.append(json.loads(line.strip()))

    @property
    def records(self) -> List[Dict[str, Any]]:
        return self._records.copy()

    @property
    def num_iterations(self) -> int:
        return len(self._records)

    def get_metric_series(self, key: str) -> List[float]:
        """Get a single metric across all iterations."""
        return [r.get(key, 0.0) for r in self._records]

    def is_monotonically_improving(self, key: str = "mean_score") -> bool:
        """Check if a metric is monotonically improving (H4 validation)."""
        series = self.get_metric_series(key)
        if len(series) < 2:
            return True
        for i in range(1, len(series)):
            if series[i] < series[i - 1] - 0.01:
                return False
        return True
