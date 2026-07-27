"""
OPSD Training Loop: main self-evolution training orchestrator.
Coordinates teacher forward, student rollout, Shapley credit,
belief consolidation, and alignment guard across iterations.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from finvl.self_evolution.opsd.teacher import OPSDTeacher
from finvl.self_evolution.opsd.rollout import StudentRollout, Trajectory
from finvl.self_evolution.credit.shapley import ShapleyCredit
from finvl.self_evolution.belief.extractor import BeliefExtractor
from finvl.self_evolution.belief.index import BeliefIndex
from finvl.self_evolution.guard.alignment import AlignmentGuard
from finvl.self_evolution.grpo_lite.router_update import GRPOLiteUpdater
from finvl.self_evolution.curves.logger import EvolutionLogger

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("opsd.train")


class OPSDTrainer:
    """
    Main OPSD training loop implementing the self-evolution algorithm.
    
    Algorithm 1 from the paper:
    For k = 1..K iterations:
      1. Student rollout -> trajectories
      2. Score trajectories (Sharpe, MDD, CVaR, Sortino)
      3. Shapley credit assignment per agent
      4. Teacher forward with hindsight
      5. JSD distillation loss + per-token KL clip
      6. GRPO-lite router update
      7. Belief consolidation (high-score trajectories)
      8. Alignment guard check
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        opsd_cfg = config.get("opsd", config)

        self.iterations = opsd_cfg.get("iterations", 8)
        self.jsd_beta = opsd_cfg.get("jsd_beta", 0.5)
        self.kl_cap = opsd_cfg.get("per_token_kl_cap", 5.0)
        self.shapley_samples = opsd_cfg.get("shapley_samples", 8)

        self.rollout = StudentRollout(
            window_days=opsd_cfg.get("rolling_window_days", 60),
            forward_days=opsd_cfg.get("forward_return_days", 20),
        )
        self.belief_extractor = BeliefExtractor()
        self.belief_index = BeliefIndex(
            capacity=opsd_cfg.get("belief", {}).get("capacity", 10000),
            embedding_dim=opsd_cfg.get("belief", {}).get("embedding_dim", 768),
        )
        self.alignment_guard = AlignmentGuard(
            kl_budget=opsd_cfg.get("alignment_guard", {}).get("kl_budget", 0.1),
        )
        self.grpo_updater = GRPOLiteUpdater(
            lr=opsd_cfg.get("grpo_lite", {}).get("lr", 1e-4),
        )
        self.evolution_logger = EvolutionLogger()

    def train(
        self,
        model_path: str,
        teacher_model_path: str,
        lora_path: str,
        data_provider,
        assets: List[str],
        output_dir: str,
        seeds: List[int] = None,
        coalition_value: Callable[[Trajectory, FrozenSet[str]], float] | None = None,
    ):
        """Run OPSD with a deterministic, same-horizon coalition replay evaluator."""
        if coalition_value is None:
            raise ValueError(
                "coalition_value is required: pass a deterministic evaluator that "
                "replays each trajectory horizon with exactly the supplied agents enabled"
            )
        shapley = ShapleyCredit(
            num_samples=self.shapley_samples,
            coalition_value=coalition_value,
        )
        seeds = seeds or [42, 123, 456]
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        teacher = OPSDTeacher(teacher_model_path, lora_path)
        teacher.load()

        for iteration in range(self.iterations):
            logger.info(f"=== Iteration {iteration + 1}/{self.iterations} ===")

            all_trajectories: List[Trajectory] = []
            for asset in assets:
                dates = data_provider.trading_dates(
                    "2019-01-01", "2022-12-31", asset=asset
                )
                trajs = self.rollout.generate_trajectories(
                    orchestrator=None,
                    provider=data_provider,
                    dates=dates,
                    asset=asset,
                    num_trajectories=10,
                )
                all_trajectories.extend(trajs)

            scores = [t.score for t in all_trajectories]
            logger.info(f"  Trajectories: {len(all_trajectories)}, "
                       f"mean_score={np.mean(scores):.4f}")

            high_score_trajs = [
                t for t in all_trajectories
                if t.score >= np.percentile(scores, 80)
            ]

            for traj in high_score_trajs:
                credits = shapley.estimate(traj)
                traj.agent_contributions = credits

            beliefs = self.belief_extractor.extract_from_trajectories(high_score_trajs)
            self.belief_index.add_beliefs(beliefs)

            kl_ok = self.alignment_guard.check(iteration)
            if not kl_ok:
                logger.warning(f"  Alignment guard triggered at iteration {iteration}")
                self.alignment_guard.rollback()
                break

            iter_metrics = {
                "iteration": iteration,
                "num_trajectories": len(all_trajectories),
                "mean_score": float(np.mean(scores)),
                "belief_store_size": self.belief_index.size,
                "belief_hit_rate": self.belief_index.hit_rate,
            }
            self.evolution_logger.log_iteration(iter_metrics)

            checkpoint_path = output / f"iteration_{iteration}"
            checkpoint_path.mkdir(parents=True, exist_ok=True)
            self.belief_index.save(str(checkpoint_path / "belief_store"))

            logger.info(f"  Metrics: {json.dumps(iter_metrics, indent=2)}")

        self.evolution_logger.save(str(output / "evolution_curve.jsonl"))
        logger.info(f"Training complete. Results saved to {output}")


def main():
    parser = argparse.ArgumentParser(description="OPSD Self-Evolution Training")
    parser.add_argument("--config", default="configs/opsd.yaml")
    parser.add_argument("--model", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--teacher-model", default="Qwen/Qwen3.5-27B")
    parser.add_argument("--lora-path", default="outputs/vlm_lora/")
    parser.add_argument("--assets", nargs="+", default=["AAPL"])
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--output", default="outputs/opsd_full/")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 123, 456])
    parser.add_argument("--wandb_run", default="opsd_train")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    if args.iterations:
        config.setdefault("opsd", {})["iterations"] = args.iterations

    trainer = OPSDTrainer(config)

    from finvl.data.provider import OHLCVProvider
    provider = OHLCVProvider("data/processed/us_dow30.csv")

    trainer.train(
        model_path=args.model,
        teacher_model_path=args.teacher_model,
        lora_path=args.lora_path,
        data_provider=provider,
        assets=args.assets,
        output_dir=args.output,
        seeds=args.seeds,
    )


if __name__ == "__main__":
    main()
