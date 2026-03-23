from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader


@dataclass
class TrainConfig:
    epochs: int = 5
    lr: float = 1e-3
    weight_decay: float = 1e-5
    lambda_align: float = 0.2
    lambda_factor: float = 0.2
    device: str = "cpu"


def _step(model, batch, cfg: TrainConfig):
    out = model(batch["image"], batch["text_feat"], batch["ts_feat"])
    ce = F.cross_entropy(out["direction_logits"], batch["direction"])
    align = F.mse_loss(out["align_score"], batch["align_target"])
    factor = F.mse_loss(out["factor_pred"], batch["factor_target"])
    loss = ce + cfg.lambda_align * align + cfg.lambda_factor * factor
    return loss, out


def run_train(model, train_loader: DataLoader, valid_loader: DataLoader, cfg: TrainConfig, output_dir: str) -> Dict[str, float]:
    device = torch.device(cfg.device)
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)

    best_val = float("inf")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        train_loss = 0.0
        n_train = 0
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            loss, _ = _step(model, batch, cfg)
            loss.backward()
            optimizer.step()
            train_loss += float(loss.item())
            n_train += 1

        model.eval()
        val_loss = 0.0
        val_acc = 0.0
        n_val = 0
        with torch.no_grad():
            for batch in valid_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                loss, out = _step(model, batch, cfg)
                val_loss += float(loss.item())
                pred = out["direction_logits"].argmax(dim=-1)
                val_acc += float((pred == batch["direction"]).float().mean().item())
                n_val += 1

        train_loss /= max(n_train, 1)
        val_loss /= max(n_val, 1)
        val_acc /= max(n_val, 1)
        print(f"epoch={epoch} train_loss={train_loss:.4f} val_loss={val_loss:.4f} val_acc={val_acc:.4f}")

        if val_loss < best_val:
            best_val = val_loss
            torch.save(model.state_dict(), out_dir / "best_visual_sft.pt")

    return {"best_val_loss": best_val}
