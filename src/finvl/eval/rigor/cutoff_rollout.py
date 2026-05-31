"""
Cutoff-aware Rollout: ensures evaluation dates strictly post-date
all model pretraining cutoffs to prevent data leakage.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml

logger = logging.getLogger(__name__)


class CutoffAwareEvaluator:
    """
    Filters evaluation dates based on model pretraining cutoffs.
    Ensures no data leakage in test results.
    """

    def __init__(self, cutoffs_path: str = "configs/cutoffs.yaml"):
        self.cutoffs = self._load_cutoffs(cutoffs_path)
        self.test_start = self.cutoffs.get("test_start", "2025-01-01")
        self.test_end = self.cutoffs.get("test_end", "2025-12-31")
        self.live_forward_start = self.cutoffs.get("live_forward_start", "2026-05-01")

    def _load_cutoffs(self, path: str) -> Dict[str, str]:
        p = Path(path)
        if not p.exists():
            logger.warning(f"Cutoffs file not found: {path}")
            return {}
        with open(p, "r") as f:
            return yaml.safe_load(f)

    def filter_dates(
        self, dates: List[str], model_name: str = "qwen2.5-vl-7b"
    ) -> List[str]:
        """Filter dates to only include those after model cutoff."""
        model_cutoffs = self.cutoffs.get("model_cutoffs", {})
        cutoff = model_cutoffs.get(model_name, "2024-01")

        cutoff_date = cutoff + "-01" if len(cutoff) == 7 else cutoff
        filtered = [d for d in dates if d > cutoff_date]

        logger.info(
            f"Cutoff filter ({model_name}): {len(dates)} -> {len(filtered)} dates "
            f"(cutoff: {cutoff_date})"
        )
        return filtered

    def get_post_cutoff_dates(self, dates: List[str]) -> List[str]:
        """Get dates that are strictly in the post-cutoff evaluation window."""
        return [d for d in dates if d >= self.live_forward_start]

    def validate_no_leakage(self, test_dates: List[str], model_name: str) -> bool:
        """Validate that all test dates are after model cutoff."""
        model_cutoffs = self.cutoffs.get("model_cutoffs", {})
        cutoff = model_cutoffs.get(model_name, "2024-01") + "-01"

        violations = [d for d in test_dates if d <= cutoff]
        if violations:
            logger.error(
                f"Data leakage detected: {len(violations)} dates before "
                f"{model_name} cutoff ({cutoff})"
            )
            return False
        return True
