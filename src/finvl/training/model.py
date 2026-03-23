from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn
import torch.nn.functional as F


class FrozenMLPEncoder(nn.Module):
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(in_dim, out_dim), nn.GELU(), nn.Linear(out_dim, out_dim))
        for p in self.parameters():
            p.requires_grad = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return self.net(x)


class VisualEncoder(nn.Module):
    def __init__(self, emb_dim: int = 128):
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Conv2d(3, 32, 3, 2, 1),
            nn.BatchNorm2d(32),
            nn.GELU(),
            nn.Conv2d(32, 64, 3, 2, 1),
            nn.BatchNorm2d(64),
            nn.GELU(),
            nn.Conv2d(64, 128, 3, 2, 1),
            nn.BatchNorm2d(128),
            nn.GELU(),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.proj = nn.Linear(128, emb_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.proj(self.backbone(x).flatten(1))


class VisualSFTModel(nn.Module):
    """Freeze text/time encoders and train visual encoder only."""

    def __init__(self, text_dim: int = 8, ts_dim: int = 8, emb_dim: int = 128, factor_dim: int = 4):
        super().__init__()
        self.visual = VisualEncoder(emb_dim)
        self.text_encoder = FrozenMLPEncoder(text_dim, emb_dim)
        self.ts_encoder = FrozenMLPEncoder(ts_dim, emb_dim)
        self.direction_head = nn.Linear(emb_dim, 3)
        self.factor_head = nn.Linear(emb_dim, factor_dim)

    def forward(self, image: torch.Tensor, text_feat: torch.Tensor, ts_feat: torch.Tensor) -> Dict[str, torch.Tensor]:
        visual_emb = self.visual(image)
        text_emb = self.text_encoder(text_feat)
        ts_emb = self.ts_encoder(ts_feat)
        target_emb = F.normalize(text_emb + ts_emb, dim=-1)
        visual_norm = F.normalize(visual_emb, dim=-1)
        align_score = torch.sum(visual_norm * target_emb, dim=-1)
        return {
            "visual_emb": visual_emb,
            "align_score": align_score,
            "direction_logits": self.direction_head(visual_emb),
            "factor_pred": self.factor_head(visual_emb),
        }
