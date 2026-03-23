from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from finvl.data.schema import DecisionSample, FinVLDataset

FACTOR_ORDER = ["trend_strength", "volatility_cluster", "momentum_5d", "volume_spike"]


def _safe_float(v: Optional[float], default: float = 0.0) -> float:
    if v is None:
        return default
    if isinstance(v, float) and math.isnan(v):
        return default
    return float(v)


class AlignedDecisionDataset(Dataset):
    def __init__(self, jsonl_path: str, images_root: Optional[str] = None, image_size: int = 224, split: str = ""):
        self.ds = FinVLDataset.load_jsonl(jsonl_path)
        self.samples: List[DecisionSample] = self.ds.samples
        if split:
            self.samples = [s for s in self.samples if (s.split or "") == split]
        self.images_root = Path(images_root) if images_root else Path(jsonl_path).parent / "charts"
        self.image_size = image_size

    def __len__(self) -> int:
        return len(self.samples)

    def _load_image(self, sample: DecisionSample) -> torch.Tensor:
        rel = sample.chart_image.image_path if sample.chart_image else ""
        p = self.images_root / rel
        if not p.exists():
            p = Path(rel)
        img = Image.open(p).convert("RGB").resize((self.image_size, self.image_size))
        arr = np.asarray(img, dtype=np.float32) / 255.0
        arr = (arr - 0.5) / 0.5
        return torch.from_numpy(arr.transpose(2, 0, 1))

    def _build_text_feat(self, sample: DecisionSample) -> torch.Tensor:
        tc = sample.textual_context
        summary = tc.combined_summary if tc else ""
        feat = np.array([
            min(len(summary) / 1500.0, 1.0),
            min((len(tc.filings) if tc else 0) / 6.0, 1.0),
            min((len(tc.news) if tc else 0) / 10.0, 1.0),
            min((len(tc.analyst_reports) if tc else 0) / 5.0, 1.0),
            1.0 if (tc and tc.has_text) else 0.0,
            float(sample.lookback_window) / 120.0,
            0.0,
            0.0,
        ], dtype=np.float32)
        return torch.from_numpy(feat)

    def _build_ts_feat(self, sample: DecisionSample) -> torch.Tensor:
        ts = sample.time_series
        if ts is None or not ts.close:
            return torch.zeros(8, dtype=torch.float32)

        close = np.array(ts.close, dtype=np.float32)
        dr = np.array(ts.daily_returns or [0.0] * len(close), dtype=np.float32)
        rsi = np.array(ts.rsi_14 or [50.0] * len(close), dtype=np.float32)
        feat = np.array([
            float(close[-1] / max(close.mean(), 1e-6) - 1.0),
            float(np.mean(dr[-5:])) if len(dr) >= 5 else float(np.mean(dr)),
            float(np.std(dr[-20:])) if len(dr) >= 20 else float(np.std(dr)),
            float(rsi[-1] / 100.0),
            float((max(close) - min(close)) / max(close[-1], 1e-6)),
            float(np.mean(close[-20:]) / max(close[-1], 1e-6) - 1.0) if len(close) >= 20 else 0.0,
            0.0,
            0.0,
        ], dtype=np.float32)
        return torch.from_numpy(feat)

    def _build_factor_target(self, sample: DecisionSample) -> torch.Tensor:
        out = np.zeros(len(FACTOR_ORDER), dtype=np.float32)
        aligns = sample.chart_image.factor_alignments if sample.chart_image else []
        by_id = {a.factor_id: float(a.score) for a in aligns}
        for i, fid in enumerate(FACTOR_ORDER):
            out[i] = by_id.get(fid, 0.0)
        return torch.from_numpy(out)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        s = self.samples[idx]
        label = (s.label or {}).get("direction", "flat")
        direction = {"down": 0, "flat": 1, "up": 2}.get(label, 1)
        ret_1d = _safe_float((s.label or {}).get("forward_return_1d"), 0.0)
        align_target = float(np.tanh(ret_1d * 20.0))
        return {
            "image": self._load_image(s),
            "text_feat": self._build_text_feat(s),
            "ts_feat": self._build_ts_feat(s),
            "direction": torch.tensor(direction, dtype=torch.long),
            "align_target": torch.tensor(align_target, dtype=torch.float32),
            "factor_target": self._build_factor_target(s),
        }
