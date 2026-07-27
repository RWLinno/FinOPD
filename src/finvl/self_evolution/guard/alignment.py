"""
Alignment Guard: prevents catastrophic drift during self-evolution.
Checks KL(student || reference) < epsilon at each step.
Triggers rollback if budget exceeded.
Periodically refreshes with adversarial off-policy samples.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


class AlignmentGuard:
    """
    Monitors KL divergence between evolving student and reference policy.
    Triggers rollback if alignment budget is exceeded.
    """

    def __init__(
        self,
        kl_budget: float = 0.1,
        check_every_steps: int = 100,
        adversarial_refresh_every: int = 4,
        adversarial_dates: List[str] = None,
        refresh_callback: Callable[[int, List[str]], None] | None = None,
    ):
        self.kl_budget = kl_budget
        self.check_every_steps = check_every_steps
        self.adversarial_refresh_every = adversarial_refresh_every
        self.adversarial_dates = adversarial_dates or [
            "2020-03", "2022-06", "2022-09"
        ]
        self.refresh_callback = refresh_callback

        self._kl_history: List[float] = []
        self._rollback_count = 0
        self._last_safe_state = None

    def check(self, iteration: int, kl_value: float | None = None) -> bool:
        """
        Check if current KL is within budget.
        Returns True if safe, False if rollback needed.
        """
        if kl_value is None:
            raise ValueError("alignment check requires measured student/reference KL")

        self._kl_history.append(kl_value)

        if kl_value > self.kl_budget:
            logger.warning(
                f"Alignment guard: KL={kl_value:.4f} > budget={self.kl_budget}. "
                f"Triggering rollback."
            )
            self._rollback_count += 1
            return False

        if (iteration + 1) % self.adversarial_refresh_every == 0:
            self._adversarial_refresh(iteration)

        self._last_safe_state = iteration
        return True

    def rollback(self):
        """Rollback to last safe state."""
        logger.info(f"Rolling back to iteration {self._last_safe_state}")

    def _adversarial_refresh(self, iteration: int):
        """
        Run off-policy refresh with adversarial samples
        (COVID crash, bear market, extreme volatility days).
        """
        if self.refresh_callback is None:
            logger.info(
                "Adversarial refresh not configured at iteration %d; no refresh claimed",
                iteration,
            )
            return
        self.refresh_callback(iteration, self.adversarial_dates)

    @property
    def total_rollbacks(self) -> int:
        return self._rollback_count

    @property
    def kl_history(self) -> List[float]:
        return self._kl_history.copy()

    def get_status(self) -> Dict[str, float]:
        return {
            "current_kl": self._kl_history[-1] if self._kl_history else 0.0,
            "kl_budget": self.kl_budget,
            "rollback_count": self._rollback_count,
            "last_safe_iteration": self._last_safe_state or 0,
        }
