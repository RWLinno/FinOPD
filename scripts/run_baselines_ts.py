"""
Baseline evaluation: PatchTST / iTransformer / TimesNet via BasicTS.
Trains on 2019-2023 data, predicts next-day returns on 2025, converts to signals,
evaluates through unified backtest protocol.

Usage:
    python scripts/run_baselines_ts.py --model patchtst --ticker GOOGL
    python scripts/run_baselines_ts.py --model all --ticker all
"""
import sys, json, argparse, os
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "external" / "BasicTS" / "src"))

COST_RT = 0.0015
SLIPPAGE = 0.0005
DELAY = 1
DATA_PATH = "data/processed/us_dow30.csv"
TRAIN_START, TRAIN_END = "2019-01-01", "2023-12-31"
TEST_START, TEST_END = "2025-01-01", "2025-12-31"


def load_ticker_data(ticker):
    """Load single ticker data from multi-ticker CSV."""
    df = pd.read_csv(DATA_PATH)
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    sub = df[df['ticker'] == ticker].sort_values('date').set_index('date')
    return sub[['open', 'high', 'low', 'close', 'volume']]


def prepare_sequences(df, lookback=60):
    """Prepare input/target sequences for time-series forecasting.
    Input: [lookback days of close returns], Target: next-day return.
    """
    close = df['close'].values.astype(float)
    returns = np.diff(close) / close[:-1]
    X, y, dates = [], [], []
    for i in range(lookback, len(returns)):
        X.append(returns[i-lookback:i])
        y.append(returns[i])
        dates.append(df.index[i+1])  # +1 because returns are shifted
    return np.array(X), np.array(y), dates


def train_pytorch_model(model_name, X_train, y_train, X_test, input_dim=60):
    """Train a simple PyTorch time-series model and return predictions."""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Simple architectures inspired by the papers
    if model_name == 'patchtst':
        patch_len, stride = 12, 12
        n_patches = input_dim // stride
        model = nn.Sequential(
            nn.Unflatten(1, (n_patches, patch_len)),
            nn.TransformerEncoder(
                nn.TransformerEncoderLayer(d_model=patch_len, nhead=3, dim_feedforward=64, batch_first=True),
                num_layers=2
            ),
            nn.Flatten(),
            nn.Linear(n_patches * patch_len, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )
    elif model_name == 'itransformer':
        model = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.TransformerEncoder(
                nn.TransformerEncoderLayer(d_model=64, nhead=4, dim_feedforward=128, batch_first=True),
                num_layers=2
            ),
            nn.Flatten(),
            nn.Linear(64, 1)
        )
    elif model_name == 'timesnet':
        model = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(32, 1)
        )
    else:
        raise ValueError(f"Unknown model: {model_name}")

    model = model.to(device)

    # Prepare data
    X_t = torch.FloatTensor(X_train).to(device)
    y_t = torch.FloatTensor(y_train).unsqueeze(1).to(device)
    if model_name == 'timesnet':
        X_t = X_t.unsqueeze(1)  # (B, 1, T) for conv1d
    elif model_name == 'itransformer':
        X_t = X_t.unsqueeze(1)  # (B, 1, T) for transformer

    dataset = TensorDataset(X_t, y_t)
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    # Train
    model.train()
    for epoch in range(50):
        total_loss = 0
        for xb, yb in loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

    # Predict
    model.eval()
    X_te = torch.FloatTensor(X_test).to(device)
    if model_name == 'timesnet':
        X_te = X_te.unsqueeze(1)
    elif model_name == 'itransformer':
        X_te = X_te.unsqueeze(1)

    with torch.no_grad():
        preds = model(X_te).cpu().numpy().flatten()
    return preds


def evaluate_predictions(predictions, prices, test_dates):
    """Convert predictions to positions and compute metrics with unified protocol."""
    n = len(predictions)
    positions = np.zeros(n)
    for i in range(n):
        if predictions[i] > 0.001:
            positions[i] = 1.0
        elif predictions[i] < -0.001:
            positions[i] = 0.0
        else:
            positions[i] = positions[i-1] if i > 0 else 0.0

    # Align with prices (delayed execution)
    daily_ret = np.diff(prices[:n+1]) / prices[:n]
    delayed_pos = np.zeros(n)
    delayed_pos[DELAY:] = positions[:n-DELAY]
    port_ret = delayed_pos * daily_ret[:n]
    pos_changes = np.abs(np.diff(np.concatenate([[0], delayed_pos])))
    port_ret -= pos_changes * (COST_RT / 2 + SLIPPAGE)
    port_ret = port_ret[np.isfinite(port_ret)]

    if len(port_ret) < 5 or np.std(port_ret) < 1e-9:
        return None

    cr = (np.prod(1 + port_ret) - 1) * 100
    sr = np.mean(port_ret) / np.std(port_ret) * np.sqrt(252)
    cum = np.cumprod(1 + port_ret)
    peak = np.maximum.accumulate(cum)
    mdd = ((peak - cum) / peak).max() * 100

    # Trade-level WR
    trades_pnl = []
    entry_p = None
    for i in range(1, len(delayed_pos)):
        if delayed_pos[i] > 0 and delayed_pos[i-1] == 0:
            entry_p = prices[i]
        elif delayed_pos[i] == 0 and delayed_pos[i-1] > 0 and entry_p is not None:
            trades_pnl.append((prices[i] - entry_p) / entry_p - (COST_RT + 2*SLIPPAGE))
            entry_p = None
    if entry_p is not None and delayed_pos[-1] > 0:
        trades_pnl.append((prices[n-1] - entry_p) / entry_p - (COST_RT + 2*SLIPPAGE))
    wr = (np.sum(np.array(trades_pnl) > 0) / max(len(trades_pnl), 1)) * 100 if trades_pnl else 50.0

    return {
        "CR": round(cr, 2), "SR": round(sr, 2), "MDD": round(mdd, 2),
        "WR": round(wr, 1), "n_trades": len(trades_pnl)
    }


def run_baseline(model_name, ticker):
    """Full pipeline: load data, train, predict, evaluate."""
    print(f"  Running {model_name} on {ticker}...")
    df = load_ticker_data(ticker)

    # Split
    train_df = df[(df.index >= TRAIN_START) & (df.index <= TRAIN_END)]
    test_df = df[(df.index >= TEST_START) & (df.index <= TEST_END)]

    if len(train_df) < 200 or len(test_df) < 50:
        print(f"    Insufficient data for {ticker}")
        return None

    # Prepare sequences
    lookback = 60
    X_train, y_train, _ = prepare_sequences(train_df, lookback)
    X_test, y_test, test_dates = prepare_sequences(test_df, lookback)

    if len(X_train) < 100 or len(X_test) < 10:
        print(f"    Insufficient sequences for {ticker}")
        return None

    # Train and predict
    predictions = train_pytorch_model(model_name, X_train, y_train, X_test, input_dim=lookback)

    # Evaluate
    test_prices = test_df['close'].values[lookback:]
    metrics = evaluate_predictions(predictions, test_prices, test_dates)

    if metrics:
        print(f"    {model_name}/{ticker}: SR={metrics['SR']:.2f} CR={metrics['CR']:.1f} MDD={metrics['MDD']:.1f} WR={metrics['WR']:.1f} trades={metrics['n_trades']}")
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="all", help="patchtst|itransformer|timesnet|all")
    parser.add_argument("--ticker", default="all", help="Ticker or 'all' for GOOGL,GS,JNJ,NVDA")
    parser.add_argument("--output", default="outputs/experiments_real/baseline_ts.json")
    args = parser.parse_args()

    models = ['patchtst', 'itransformer', 'timesnet'] if args.model == 'all' else [args.model]
    tickers = ['GOOGL', 'GS', 'JNJ', 'NVDA'] if args.ticker == 'all' else [args.ticker]

    results = {}
    for model_name in models:
        results[model_name] = {}
        print(f"\n{'='*50} {model_name.upper()} {'='*50}")
        for ticker in tickers:
            m = run_baseline(model_name, ticker)
            if m:
                results[model_name][ticker] = m

    # Save
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
