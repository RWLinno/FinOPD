"""
Synthetic test data generator for FinVL-MAS.

Generates realistic-looking OHLCV data with embedded chart patterns,
synthetic news/filing text, and aligned tri-modal samples.
Used for development, testing, and pipeline validation.
"""

from __future__ import annotations

import logging
import os
import random
from typing import List, Optional

import numpy as np
import pandas as pd

from finvl.data.schema import (
    AnalystReport,
    DecisionSample,
    FilingItem,
    FinVLDataset,
    NewsItem,
    TextualContext,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Synthetic OHLCV Generation
# ──────────────────────────────────────────────

def generate_synthetic_ohlcv(
    n_bars: int = 500,
    start_date: str = "2022-01-03",
    start_price: float = 100.0,
    volatility: float = 0.02,
    trend: float = 0.0003,
    freq: str = "B",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with realistic properties:
    - Geometric Brownian Motion for prices
    - Intraday range proportional to volatility
    - Volume correlated with price moves
    - Embedded regime changes
    """
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start=start_date, periods=n_bars, freq=freq)

    # Price with regime changes
    prices = np.zeros(n_bars)
    prices[0] = start_price
    regimes = _generate_regimes(n_bars, rng)

    for i in range(1, n_bars):
        regime_vol = volatility * regimes[i]
        regime_trend = trend * (1.5 if regimes[i] < 1.0 else 0.5 if regimes[i] > 1.5 else 1.0)
        ret = regime_trend + regime_vol * rng.randn()
        prices[i] = prices[i - 1] * (1 + ret)

    # Generate OHLCV from close prices
    opens = np.zeros(n_bars)
    highs = np.zeros(n_bars)
    lows = np.zeros(n_bars)
    volumes = np.zeros(n_bars)

    opens[0] = prices[0] * (1 + rng.randn() * 0.002)
    for i in range(1, n_bars):
        gap = rng.randn() * volatility * 0.3
        opens[i] = prices[i - 1] * (1 + gap)

    for i in range(n_bars):
        spread = abs(prices[i] - opens[i])
        extra_range = abs(rng.randn()) * volatility * prices[i] * 0.5
        highs[i] = max(opens[i], prices[i]) + extra_range
        lows[i] = min(opens[i], prices[i]) - extra_range * rng.uniform(0.5, 1.0)

        # Volume: higher on big moves
        base_vol = 1_000_000
        move_factor = 1.0 + 3.0 * abs(prices[i] - opens[i]) / prices[i]
        volumes[i] = max(50_000, base_vol * move_factor * (0.5 + rng.rand()))

    df = pd.DataFrame({
        "open": np.round(opens, 2),
        "high": np.round(highs, 2),
        "low": np.round(lows, 2),
        "close": np.round(prices, 2),
        "volume": volumes.astype(int),
    }, index=dates)
    df.index.name = "date"

    return df


def _generate_regimes(n: int, rng: np.random.RandomState) -> np.ndarray:
    """Generate volatility regime multipliers (periods of calm and storm)."""
    regimes = np.ones(n)
    i = 0
    while i < n:
        regime_len = rng.randint(20, 80)
        regime_type = rng.choice(["calm", "normal", "volatile"], p=[0.25, 0.50, 0.25])
        mult = {"calm": 0.6, "normal": 1.0, "volatile": 1.8}[regime_type]
        end = min(i + regime_len, n)
        regimes[i:end] = mult
        i = end
    return regimes


# ──────────────────────────────────────────────
# Synthetic Text Generation
# ──────────────────────────────────────────────

_NEWS_TEMPLATES_BULL = [
    "{asset} reports strong quarterly earnings, beating analyst expectations by {pct}%.",
    "Analysts upgrade {asset} to 'Buy' with a target price of ${target:.0f}.",
    "{asset} announces strategic partnership to expand into new markets.",
    "Institutional investors increase stake in {asset} by {pct}% this quarter.",
    "{asset}'s new product launch receives positive market reception.",
    "Revenue growth of {pct}% year-over-year for {asset} exceeds forecasts.",
]

_NEWS_TEMPLATES_BEAR = [
    "{asset} misses earnings estimates; guidance lowered for next quarter.",
    "Analysts downgrade {asset} to 'Sell' citing {reason}.",
    "{asset} faces regulatory investigation over {reason}.",
    "Key executive departure at {asset} raises concerns among investors.",
    "{asset}'s market share declines amid intensifying competition.",
    "Supply chain disruptions impact {asset}'s production capacity.",
]

_NEWS_TEMPLATES_NEUTRAL = [
    "{asset} announces share buyback program worth ${amount}M.",
    "{asset} to present at upcoming investor conference next week.",
    "Industry report highlights mixed outlook for {asset}'s sector.",
    "{asset} maintains current dividend policy at ${div:.2f} per share.",
]

_FILING_TEMPLATES = [
    "Management's Discussion and Analysis: Revenue for {period} was ${rev:.0f}M, "
    "representing a {growth}% change from the prior period. Operating margins "
    "{margin_direction} to {margin:.1f}%. The company {outlook} for the upcoming period.",
    "Risk Factors: The company faces {risk1}. Additionally, {risk2}. "
    "Market conditions remain {conditions} with {outlook_qualifier} visibility.",
]

_REASONS = ["competitive pressure", "margin compression", "regulatory concerns",
            "management changes", "declining growth", "market saturation"]

_RISKS = ["supply chain disruptions", "foreign currency headwinds",
          "rising interest rates", "increased competition", "regulatory changes"]


def generate_synthetic_text(
    asset: str,
    date: str,
    price: float,
    returns_5d: float,
    rng: Optional[np.random.RandomState] = None,
) -> TextualContext:
    """Generate synthetic but realistic-looking textual context for a decision date."""
    rng = rng or np.random.RandomState()

    # Decide sentiment based on recent returns (correlated, not perfect)
    base_sentiment = np.clip(returns_5d * 20, -1, 1)
    noise = rng.randn() * 0.3
    sentiment = np.clip(base_sentiment + noise, -1, 1)

    news_items: List[NewsItem] = []
    n_news = rng.randint(0, 4)

    for i in range(n_news):
        days_back = rng.randint(0, 5)
        news_date = (pd.Timestamp(date) - pd.Timedelta(days=days_back)).strftime("%Y-%m-%d")

        if sentiment > 0.2:
            tmpl = rng.choice(_NEWS_TEMPLATES_BULL)
        elif sentiment < -0.2:
            tmpl = rng.choice(_NEWS_TEMPLATES_BEAR)
        else:
            tmpl = rng.choice(_NEWS_TEMPLATES_NEUTRAL)

        headline = tmpl.format(
            asset=asset,
            pct=rng.randint(3, 25),
            target=price * (1 + rng.uniform(0.05, 0.25)),
            reason=rng.choice(_REASONS),
            amount=rng.randint(100, 2000),
            div=rng.uniform(0.5, 3.0),
        )
        news_items.append(NewsItem(
            date=news_date, headline=headline,
            source=rng.choice(["Reuters", "Bloomberg", "CNBC", "MarketWatch"]),
            sentiment=round(float(sentiment + rng.randn() * 0.15), 2),
            relevance=round(float(rng.uniform(0.5, 1.0)), 2),
        ))

    # Generate filing with ~30% probability
    filings: List[FilingItem] = []
    if rng.rand() < 0.3:
        tmpl = rng.choice(_FILING_TEMPLATES)
        month = pd.Timestamp(date).month
        quarter = (month - 1) // 3 + 1
        content = tmpl.format(
            period=f"Q{quarter} {pd.Timestamp(date).year}",
            rev=rng.uniform(500, 5000),
            growth=rng.randint(-15, 30),
            margin_direction=rng.choice(["improved", "declined", "remained stable"]),
            margin=rng.uniform(5, 35),
            outlook=rng.choice([
                "maintains a cautious but optimistic outlook",
                "expects continued growth momentum",
                "acknowledges near-term headwinds",
            ]),
            risk1=rng.choice(_RISKS),
            risk2=rng.choice(_RISKS),
            conditions=rng.choice(["challenging", "favorable", "uncertain"]),
            outlook_qualifier=rng.choice(["limited", "moderate", "improving"]),
        )
        filings.append(FilingItem(
            date=date, filing_type=rng.choice(["10-Q", "10-K"]),
            section="Item 7 - MD&A", content=content,
            fiscal_period=f"Q{quarter} {pd.Timestamp(date).year}",
        ))

    # Generate analyst report with ~20% probability
    reports: List[AnalystReport] = []
    if rng.rand() < 0.2:
        if sentiment > 0.3:
            rating = rng.choice(["strong_buy", "buy"])
        elif sentiment < -0.3:
            rating = rng.choice(["sell", "hold"])
        else:
            rating = "hold"
        reports.append(AnalystReport(
            date=date, source=rng.choice(["Zacks", "Morningstar", "S&P", "Goldman Sachs"]),
            rating=rating,
            target_price=round(float(price * (1 + rng.uniform(-0.1, 0.2))), 2),
            summary=f"Analyst maintains {rating} rating based on recent performance trends.",
        ))

    # Combined summary
    parts = []
    if news_items:
        parts.append(f"{len(news_items)} recent news items (sentiment: {sentiment:+.2f})")
    if filings:
        parts.append(f"Recent {filings[0].filing_type} filing available")
    if reports:
        parts.append(f"Analyst rating: {reports[0].rating}")
    combined = "; ".join(parts) if parts else "No significant textual context available."

    return TextualContext(
        news=news_items, filings=filings, analyst_reports=reports,
        combined_summary=combined,
    )


# ──────────────────────────────────────────────
# Full Synthetic Dataset Builder
# ──────────────────────────────────────────────

def generate_synthetic_dataset(
    asset: str = "SYNTH",
    n_bars: int = 500,
    lookback: int = 60,
    start_date: str = "2022-01-03",
    output_dir: str = "data/synthetic",
    seed: int = 42,
    sample_every_n: int = 5,
) -> FinVLDataset:
    """
    Generate a complete synthetic tri-modal dataset.

    Produces:
    - OHLCV CSV
    - Chart images for each sample
    - Synthetic news/filings
    - Aligned JSONL dataset

    Args:
        asset: Synthetic asset name.
        n_bars: Total number of OHLCV bars.
        lookback: Lookback window for each sample.
        start_date: Start date for the series.
        output_dir: Root output directory.
        seed: Random seed for reproducibility.
        sample_every_n: Create a sample every N trading days.

    Returns:
        FinVLDataset ready for experiments.
    """
    from finvl.data.pipeline import build_dataset, compute_indicators

    rng = np.random.RandomState(seed)
    os.makedirs(output_dir, exist_ok=True)

    # Generate OHLCV
    logger.info(f"Generating {n_bars} synthetic OHLCV bars for {asset}...")
    ohlcv_df = generate_synthetic_ohlcv(
        n_bars=n_bars, start_date=start_date, seed=seed,
    )
    csv_path = os.path.join(output_dir, f"{asset}_ohlcv.csv")
    ohlcv_df.to_csv(csv_path)
    logger.info(f"Saved OHLCV to {csv_path}")

    # Pick decision dates
    all_dates = [d.strftime("%Y-%m-%d") for d in ohlcv_df.index]
    decision_dates = all_dates[lookback::sample_every_n]
    logger.info(f"Decision dates: {len(decision_dates)}")

    # Text provider using synthetic generator
    ohlcv_with_indicators = compute_indicators(ohlcv_df)

    def text_provider(asset_name: str, date: str) -> TextualContext:
        dt = pd.Timestamp(date)
        mask = ohlcv_with_indicators.index <= dt
        avail = ohlcv_with_indicators.loc[mask]
        if len(avail) < 5:
            return TextualContext()
        price = float(avail["close"].iloc[-1])
        ret_5d = float(avail["close"].iloc[-1] / avail["close"].iloc[-5] - 1) if len(avail) >= 5 else 0
        return generate_synthetic_text(asset_name, date, price, ret_5d, rng)

    # Build full dataset
    chart_dir = os.path.join(output_dir, "charts")
    dataset = build_dataset(
        ohlcv_df=ohlcv_df,
        asset=asset,
        decision_dates=decision_dates,
        chart_output_dir=chart_dir,
        lookback=lookback,
        market="synthetic",
        text_provider=text_provider,
        chart_overlays=["sma_5", "sma_20"],
    )

    # Save JSONL
    jsonl_path = os.path.join(output_dir, f"{asset}_dataset.jsonl")
    dataset.save_jsonl(jsonl_path)
    logger.info(f"Saved {len(dataset)} samples to {jsonl_path}")

    # Save metadata
    import json
    meta = {
        "asset": asset,
        "n_bars": n_bars,
        "n_samples": len(dataset),
        "lookback": lookback,
        "start_date": start_date,
        "seed": seed,
        "ohlcv_path": csv_path,
        "jsonl_path": jsonl_path,
        "chart_dir": chart_dir,
        "date_range": list(dataset.date_range),
        "modalities": ["time_series", "chart_image", "textual_context"],
    }
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    return dataset
