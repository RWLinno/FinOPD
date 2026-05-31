"""
Factor Router training: learns to select optimal factor subsets per regime.
Uses historical factor values and forward returns as supervision signal.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).parent.parent))

from finvl.factors.dsl_engine import FactorDSL
from finvl.factors.router import FactorRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_router")

REGIME_MAP = {"calm": 0, "trending": 1, "volatile": 2, "ranging": 3}


def classify_regime(close: np.ndarray, window: int = 20) -> str:
    if len(close) < window:
        return "calm"
    rets = np.diff(close[-window:]) / close[-window:-1]
    vol = np.std(rets) * np.sqrt(252)
    trend = (close[-1] / close[-window] - 1)
    if vol > 0.30:
        return "volatile"
    elif abs(trend) > 0.10:
        return "trending"
    elif vol < 0.12:
        return "calm"
    return "ranging"


def encode_regime(regime: str) -> torch.Tensor:
    idx = REGIME_MAP.get(regime, 3)
    onehot = torch.zeros(4)
    onehot[idx] = 1.0
    return onehot


class FactorReturnDataset(Dataset):
    """
    Dataset: for each date, compute all factor values and the forward return.
    Router learns to select factors whose values best predict forward returns.
    """

    def __init__(self, ohlcv_path: str, factor_json: str, lookback: int = 60,
                 forward_days: int = 5, max_samples: int = 2000):
        self.samples: List[Dict] = []
        dsl = FactorDSL()

        # Load factors
        factor_exprs = []
        with open(factor_json, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line == 'null':
                    continue
                try:
                    d = json.loads(line)
                    if d and 'expr' in d:
                        factor_exprs.append((d['name'], d['expr'], d.get('Information_Ratio_with_cost', 0)))
                except:
                    pass

        self.num_factors = len(factor_exprs)
        self.factor_names = [f[0] for f in factor_exprs]
        logger.info(f"Loading {self.num_factors} factors for router training")

        # Load OHLCV
        df = pd.read_csv(ohlcv_path, parse_dates=True, index_col=0)
        df.columns = [c.lower() for c in df.columns]

        # Generate samples
        dates = df.index[lookback:-forward_days]
        if max_samples and len(dates) > max_samples:
            indices = np.linspace(0, len(dates)-1, max_samples, dtype=int)
            dates = dates[indices]

        for dt in dates:
            loc = df.index.get_loc(dt)
            window = df.iloc[loc-lookback:loc+1]
            forward_close = df['close'].iloc[loc:loc+forward_days+1]

            if len(window) < lookback or len(forward_close) < 2:
                continue

            # Forward return
            fwd_ret = (forward_close.iloc[-1] / forward_close.iloc[0]) - 1

            # Regime
            regime = classify_regime(window['close'].values)

            # Compute all factor values at this date
            factor_vals = np.zeros(self.num_factors)
            for i, (name, expr, ir) in enumerate(factor_exprs):
                try:
                    result = dsl.evaluate(expr, window)
                    val = result.iloc[-1]
                    if np.isfinite(val):
                        factor_vals[i] = val
                except:
                    pass

            # Factor "returns": correlation of factor value with forward return
            # Positive factor value * positive forward return = good selection
            factor_rewards = factor_vals * np.sign(fwd_ret) * abs(fwd_ret) * 100

            self.samples.append({
                'regime': regime,
                'factor_vals': factor_vals,
                'factor_rewards': factor_rewards,
                'fwd_ret': fwd_ret,
            })

        logger.info(f"Built {len(self.samples)} training samples")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        # Use factor values as "geometry embedding" (simplified)
        geo_emb = torch.tensor(s['factor_vals'][:768], dtype=torch.float32)
        if len(geo_emb) < 768:
            geo_emb = torch.cat([geo_emb, torch.zeros(768 - len(geo_emb))])
        regime_onehot = encode_regime(s['regime'])
        factor_rewards = torch.tensor(s['factor_rewards'], dtype=torch.float32)
        return {
            'geometry_emb': geo_emb,
            'regime_onehot': regime_onehot,
            'factor_rewards': factor_rewards,
        }


def train_router(
    ohlcv_path: str,
    factor_json: str,
    output_dir: str,
    epochs: int = 30,
    lr: float = 3e-4,
    batch_size: int = 32,
    top_k: int = 15,
    max_samples: int = 1500,
):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    dataset = FactorReturnDataset(ohlcv_path, factor_json, max_samples=max_samples)
    if len(dataset) < 10:
        logger.error("Not enough training samples")
        return

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)

    router = FactorRouter(
        geometry_dim=768,
        regime_dim=4,
        num_factors=dataset.num_factors,
        hidden_dim=256,
        top_k=top_k,
    )

    optimizer = optim.Adam(router.parameters(), lr=lr)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    router.to(device)

    best_loss = float("inf")
    history = []

    for epoch in range(1, epochs + 1):
        router.train()
        total_loss = 0.0
        total_reward = 0.0
        n_batches = 0

        progress = epoch / epochs
        router.anneal_tau(progress)

        for batch in loader:
            geo_emb = batch['geometry_emb'].to(device)
            regime = batch['regime_onehot'].to(device)
            rewards = batch['factor_rewards'].to(device)

            selection, logits = router(geo_emb, regime, hard=True)

            # Reward: sum of selected factor rewards
            selected_reward = (selection * rewards).sum(dim=-1) / top_k
            loss = -selected_reward.mean()

            # Entropy regularization (encourage exploration early)
            entropy = router.compute_entropy(logits)
            entropy_coeff = 0.05 * (1 - progress)
            loss = loss - entropy_coeff * entropy

            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(router.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item()
            total_reward += selected_reward.mean().item()
            n_batches += 1

        avg_loss = total_loss / max(n_batches, 1)
        avg_reward = total_reward / max(n_batches, 1)
        history.append({'epoch': epoch, 'loss': avg_loss, 'reward': avg_reward, 'tau': router.tau})

        if epoch % 5 == 0 or epoch == 1:
            logger.info(f"Epoch {epoch}/{epochs} loss={avg_loss:.4f} reward={avg_reward:.4f} tau={router.tau:.3f}")

        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save(router.state_dict(), output / "router_best.pt")

    torch.save(router.state_dict(), output / "router_final.pt")
    torch.save({
        'num_factors': dataset.num_factors,
        'top_k': top_k,
        'factor_names': dataset.factor_names,
        'best_loss': best_loss,
    }, output / "router_config.pt")

    with open(output / "training_history.json", 'w') as f:
        json.dump(history, f, indent=2)

    logger.info(f"Router training complete. Best loss: {best_loss:.4f}")
    logger.info(f"Saved to {output}")


def main():
    parser = argparse.ArgumentParser(description="Train Factor Router")
    parser.add_argument("--data", default="data/raw/AAPL_ohlcv.csv")
    parser.add_argument("--factor-json", default="docs/best_factor.json")
    parser.add_argument("--output", default="outputs/router/")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument("--max-samples", type=int, default=1500)
    args = parser.parse_args()

    train_router(
        ohlcv_path=args.data,
        factor_json=args.factor_json,
        output_dir=args.output,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        top_k=args.top_k,
        max_samples=args.max_samples,
    )


if __name__ == "__main__":
    main()
