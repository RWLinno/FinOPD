"""
OPSD Training Loop: main self-evolution training orchestrator.
Coordinates teacher forward, student rollout, Shapley credit,
belief consolidation, and alignment guard across iterations.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List

import numpy as np
import torch
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from finvl.self_evolution.opsd.rollout import StudentRollout, Trajectory
from finvl.self_evolution.credit.shapley import ShapleyCredit
from finvl.self_evolution.credit.replay import CoalitionReplayEvaluator
from finvl.self_evolution.belief.extractor import BeliefExtractor
from finvl.self_evolution.belief.index import BeliefIndex
from finvl.self_evolution.guard.alignment import AlignmentGuard
from finvl.self_evolution.curves.logger import EvolutionLogger
from finvl.self_evolution.grpo_lite.router_update import GRPOLiteUpdater

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
        belief_cfg = opsd_cfg.get("belief", {})
        self.belief_extractor = BeliefExtractor(
            embedding_dim=belief_cfg.get("embedding_dim", 768),
            admission_percentile=belief_cfg.get("admission_percentile", 80),
        )
        self.belief_index = BeliefIndex(
            capacity=belief_cfg.get("capacity", 10000),
            embedding_dim=belief_cfg.get("embedding_dim", 768),
        )
        self.alignment_guard = AlignmentGuard(
            kl_budget=opsd_cfg.get("alignment_guard", {}).get("kl_budget", 0.1),
        )
        self.evolution_logger = EvolutionLogger()
        self.train_start = opsd_cfg.get("train_start", "2019-01-01")
        self.train_end = opsd_cfg.get("train_end", "2022-12-31")
        self.num_trajectories = opsd_cfg.get("num_trajectories", 10)
        self.admission_percentile = belief_cfg.get("admission_percentile", 80)
        grpo_cfg = opsd_cfg.get("grpo_lite", {})
        self.router_update_enabled = grpo_cfg.get("enabled", False)
        self.router_updater = GRPOLiteUpdater(
            lr=grpo_cfg.get("lr", 1e-4),
            clip_eps=grpo_cfg.get("clip_eps", 0.2),
            entropy_coef=grpo_cfg.get("entropy_coef", 0.01),
        )

    def _update_router(self, orchestrator, trajectories, iteration: int):
        """Update the router from actions recorded by the accepted rollout."""
        if not self.router_update_enabled:
            return None
        router = getattr(orchestrator, "factor_router", None)
        if router is None:
            raise RuntimeError(
                "GRPO-lite is enabled but no trained factor-router checkpoint is loaded"
            )

        features = []
        regimes = []
        selections = []
        utilities = []
        for trajectory in trajectories:
            for step in trajectory.steps:
                if not (
                    step.router_features
                    and step.router_regime
                    and step.router_selected_indices
                ):
                    continue
                mask = np.zeros(router.num_factors, dtype=np.float32)
                selected = np.asarray(step.router_selected_indices, dtype=int)
                if (selected < 0).any() or (selected >= router.num_factors).any():
                    raise ValueError("rollout contains an out-of-range router factor index")
                mask[selected] = 1.0
                features.append(step.router_features)
                regimes.append(step.router_regime)
                selections.append(mask)
                utilities.append(trajectory.score)
        if not features:
            raise RuntimeError("GRPO-lite is enabled but rollout recorded no router actions")

        device = next(router.parameters()).device
        router.anneal_tau((iteration + 1) / max(self.iterations, 1))
        return self.router_updater.update(
            router,
            torch.tensor(features, dtype=torch.float32, device=device),
            torch.tensor(regimes, dtype=torch.float32, device=device),
            torch.tensor(utilities, dtype=torch.float32, device=device),
            selection_mask=torch.tensor(
                np.asarray(selections), dtype=torch.float32, device=device
            ),
        )

    def train(
        self,
        data_provider,
        assets: List[str],
        output_dir: str,
        backend,
        orchestrator,
        seed: int = 42,
        coalition_value: Callable[[Trajectory, FrozenSet[str]], float] | None = None,
    ):
        """Run OPSD with real rollout, replay credit, update, and measured KL."""
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if coalition_value is None:
            coalition_value = CoalitionReplayEvaluator(
                self.config,
                data_provider,
                self.rollout,
                policy_backend=backend,
                belief_index=self.belief_index,
            )
        shapley = ShapleyCredit(
            num_samples=self.shapley_samples,
            coalition_value=coalition_value,
        )
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        for iteration in range(self.iterations):
            logger.info(f"=== Iteration {iteration + 1}/{self.iterations} ===")
            backend.begin_iteration(iteration)
            router = getattr(orchestrator, "factor_router", None)
            router_reference = None
            if self.router_update_enabled:
                if router is None:
                    raise RuntimeError(
                        "GRPO-lite is enabled but the orchestrator has no factor router"
                    )
                router_reference = {
                    key: value.detach().cpu().clone()
                    for key, value in router.state_dict().items()
                }

            all_trajectories: List[Trajectory] = []
            for asset in assets:
                dates = data_provider.trading_dates(
                    self.train_start, self.train_end, asset=asset
                )
                trajs = self.rollout.generate_trajectories(
                    orchestrator=orchestrator,
                    provider=data_provider,
                    dates=dates,
                    asset=asset,
                    num_trajectories=self.num_trajectories,
                    belief_index=self.belief_index,
                )
                all_trajectories.extend(trajs)

            scores = [t.score for t in all_trajectories]
            if not scores:
                raise RuntimeError("student rollout produced no valid trajectories")
            logger.info(f"  Trajectories: {len(all_trajectories)}, "
                       f"mean_score={np.mean(scores):.4f}")

            high_score_trajs = [
                t for t in all_trajectories
                if t.score >= np.percentile(scores, self.admission_percentile)
            ]

            update_metrics = []
            for traj in high_score_trajs:
                credits = shapley.estimate(traj)
                traj.agent_contributions = credits
                distillation_weights = shapley.compute_distillation_weights(credits)
                update_metrics.append(backend.update(traj, distillation_weights))

            if not update_metrics:
                raise RuntimeError("no matured trajectory was selected for OPSD update")

            router_metrics = self._update_router(
                orchestrator, high_score_trajs, iteration
            )

            reference_kl = float(
                np.mean([metric["reference_kl"] for metric in update_metrics])
            )
            kl_ok = self.alignment_guard.check(iteration, reference_kl)
            if not kl_ok:
                logger.warning(f"  Alignment guard triggered at iteration {iteration}")
                self.alignment_guard.rollback()
                backend.rollback()
                if router_reference is not None:
                    router.load_state_dict(router_reference)
                break

            # Only accepted policy/router updates may mutate cross-time memory.
            beliefs = self.belief_extractor.extract_from_trajectories(high_score_trajs)
            self.belief_index.add_beliefs(beliefs)

            iter_metrics = {
                "iteration": iteration,
                "num_trajectories": len(all_trajectories),
                "mean_score": float(np.mean(scores)),
                "seed": seed,
                "opsd_loss": float(
                    np.mean([metric["opsd_loss"] for metric in update_metrics])
                ),
                "reference_kl": reference_kl,
                "teacher_student_kl": float(
                    np.mean(
                        [metric["teacher_student_kl"] for metric in update_metrics]
                    )
                ),
                "distilled_steps": int(
                    sum(metric["distilled_steps"] for metric in update_metrics)
                ),
                "belief_store_size": self.belief_index.size,
                "belief_hit_rate": self.belief_index.hit_rate,
            }
            if router_metrics is not None:
                iter_metrics.update(
                    {
                        "router_policy_loss": router_metrics["policy_loss"],
                        "router_entropy": router_metrics["entropy"],
                        "router_total_loss": router_metrics["total_loss"],
                    }
                )
            self.evolution_logger.log_iteration(iter_metrics)

            checkpoint_path = output / f"iteration_{iteration}"
            checkpoint_path.mkdir(parents=True, exist_ok=True)
            self.belief_index.save(str(checkpoint_path / "belief_store"))
            backend.save(str(checkpoint_path))
            if router is not None:
                torch.save(router.state_dict(), checkpoint_path / "router.pt")
                torch.save(
                    {
                        "num_factors": router.num_factors,
                        "top_k": router.top_k,
                        "factor_names": list(
                            getattr(orchestrator, "router_factor_names", [])
                        ),
                    },
                    checkpoint_path / "router_config.pt",
                )

            logger.info(f"  Metrics: {json.dumps(iter_metrics, indent=2)}")

        self.evolution_logger.save(str(output / "evolution_curve.jsonl"))
        logger.info(f"Training complete. Results saved to {output}")


def main():
    parser = argparse.ArgumentParser(description="OPSD Self-Evolution Training")
    parser.add_argument("--config", default="configs/opsd.yaml")
    parser.add_argument("--model", default=".models/Qwen3.5-9B")
    parser.add_argument("--teacher-model", default=".models/Qwen3.5-27B")
    parser.add_argument("--lora-path", default=None)
    parser.add_argument("--student-device", default="cuda:0")
    parser.add_argument("--teacher-device", default="cuda:1")
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

    from finvl.data.provider import OHLCVProvider
    from finvl.self_evolution.opsd.qwen_backend import LocalQwenOPSDBackend
    from finvl.workflow.orchestrator import AgentOrchestrator

    provider = OHLCVProvider("data/processed/us_dow30.csv")
    for seed in args.seeds:
        trainer = OPSDTrainer(config)
        backend = LocalQwenOPSDBackend(
            student_model=args.model,
            teacher_model=args.teacher_model,
            lora_path=args.lora_path,
            student_device=args.student_device,
            teacher_device=args.teacher_device,
            learning_rate=config["opsd"]["student"]["learning_rate"],
            lora_rank=config["opsd"]["student"]["lora_rank"],
            target_modules=config["opsd"]["student"]["lora_target_modules"],
            beta=config["opsd"]["jsd_beta"],
            kl_cap=config["opsd"]["per_token_kl_cap"],
        )
        backend.load()
        orchestrator = backend.wrap_orchestrator(AgentOrchestrator(config))
        trainer.train(
            data_provider=provider,
            assets=args.assets,
            output_dir=str(Path(args.output) / f"seed_{seed}"),
            backend=backend,
            orchestrator=orchestrator,
            seed=seed,
        )


if __name__ == "__main__":
    main()
