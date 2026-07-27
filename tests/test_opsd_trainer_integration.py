import json
from pathlib import Path

import numpy as np
import pandas as pd

from finvl.core.types import Action, Conviction, DecisionOutput
from finvl.self_evolution.opsd.qwen_backend import LocalQwenOPSDBackend
from finvl.self_evolution.opsd.train import OPSDTrainer


class FakeProvider:
    def __init__(self):
        dates = pd.date_range("2021-01-01", periods=100, freq="B")
        close = 100 * np.cumprod(1 + np.linspace(-0.002, 0.004, len(dates)))
        self.frame = pd.DataFrame(
            {
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": np.linspace(1_000_000, 2_000_000, len(dates)),
            },
            index=dates,
        )

    def trading_dates(self, _start, _end, asset=None):
        assert asset == "AAPL"
        return [date.strftime("%Y-%m-%d") for date in self.frame.index[-30:]]

    def get_window(self, end_date, lookback=60, asset=None):
        assert asset == "AAPL"
        return self.frame.loc[:pd.Timestamp(end_date)].tail(lookback).copy()

    def _asset_frame(self, asset=None):
        assert asset == "AAPL"
        return self.frame


class FakeOrchestrator:
    last_policy_prompt = "point-in-time prompt"
    last_policy_completion = '{"action":"buy"}'
    last_factor_ids = [1, 4, 9]

    async def run(self, _inputs):
        return DecisionOutput(
            action=Action.BUY,
            conviction=Conviction.MODERATE,
            position_size_pct=0.2,
            confidence=0.8,
            rationale="deterministic fake policy",
        )


class FakeBackend:
    def __init__(self):
        self.iterations = []
        self.updates = 0
        self.saved = []

    def begin_iteration(self, iteration):
        self.iterations.append(iteration)

    def update(self, trajectory, credits):
        assert trajectory.steps[0].policy_prompt
        assert set(credits) == {
            "ChartAnalyst",
            "PatternReasoner",
            "EventAnalyst",
            "RiskController",
            "DecisionPM",
        }
        self.updates += 1
        return {
            "opsd_loss": 0.2,
            "reference_kl": 0.01,
            "teacher_student_kl": 0.3,
            "distilled_steps": 4,
        }

    def save(self, output_dir):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        self.saved.append(output_dir)

    def rollback(self):
        raise AssertionError("rollback should not trigger")


def test_trainer_executes_rollout_credit_update_and_measured_kl(tmp_path):
    config = {
        "opsd": {
            "iterations": 1,
            "rolling_window_days": 20,
            "forward_return_days": 2,
            "num_trajectories": 1,
            "shapley_samples": 2,
            "belief": {
                "capacity": 10,
                "embedding_dim": 32,
                "admission_percentile": 0,
            },
            "alignment_guard": {"kl_budget": 0.1},
        }
    }
    contributions = {
        "ChartAnalyst": 0.1,
        "PatternReasoner": 0.2,
        "EventAnalyst": 0.1,
        "RiskController": 0.2,
        "DecisionPM": 0.4,
    }

    def coalition_value(_trajectory, coalition):
        return sum(contributions[agent] for agent in coalition)

    backend = FakeBackend()
    output = tmp_path / "opsd"
    trainer = OPSDTrainer(config)
    trainer.train(
        data_provider=FakeProvider(),
        assets=["AAPL"],
        output_dir=str(output),
        backend=backend,
        orchestrator=FakeOrchestrator(),
        seed=7,
        coalition_value=coalition_value,
    )

    record = json.loads((output / "evolution_curve.jsonl").read_text().strip())
    assert record["reference_kl"] == 0.01
    assert record["opsd_loss"] == 0.2
    assert record["distilled_steps"] == 4
    assert backend.updates == 1
    assert backend.saved


def test_qwen_json_scalar_coercion_is_bounded():
    parse = LocalQwenOPSDBackend._bounded_number
    assert parse("moderate", default=0.1, lower=0.0, upper=1.0) == 0.5
    assert parse("50", default=0.0, lower=0.0, upper=0.3, percent_if_gt_one=True) == 0.3
    assert parse("not-a-number", default=0.2, lower=0.0, upper=1.0) == 0.2
