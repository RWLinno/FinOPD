"""Train visual-only SFT with frozen text/time encoders."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from torch.utils.data import DataLoader, random_split

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.training.dataset import AlignedDecisionDataset
from finvl.training.model import VisualSFTModel
from finvl.training.trainer import TrainConfig, run_train


def main():
    parser = argparse.ArgumentParser(description="Train visual SFT for FinVL-MAS")
    parser.add_argument("--dataset-jsonl", required=True)
    parser.add_argument("--images-root", default=None)
    parser.add_argument("--split", default="")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--output-dir", default="outputs/checkpoints/visual_sft")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    ds = AlignedDecisionDataset(args.dataset_jsonl, images_root=args.images_root, split=args.split)
    n = len(ds)
    n_train = max(1, int(n * 0.8))
    n_val = max(1, n - n_train)
    train_ds, val_ds = random_split(ds, [n_train, n_val])

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = VisualSFTModel()
    cfg = TrainConfig(epochs=args.epochs, lr=args.lr, device=args.device)
    metrics = run_train(model, train_loader, val_loader, cfg, args.output_dir)
    print(metrics)


if __name__ == "__main__":
    main()
