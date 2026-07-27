import pandas as pd
import pytest

from finvl.data.provider import OHLCVProvider


def test_multiasset_provider_requires_and_respects_asset(tmp_path):
    rows = []
    for ticker, base in [("AAA", 10), ("BBB", 100)]:
        for i, date in enumerate(pd.date_range("2025-01-01", periods=5, freq="B")):
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "open": base + i,
                    "high": base + i + 1,
                    "low": base + i - 1,
                    "close": base + i + 0.5,
                    "volume": 1000,
                }
            )
    path = tmp_path / "bars.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    provider = OHLCVProvider(str(path))
    with pytest.raises(ValueError, match="explicit asset"):
        provider.get_window("2025-01-07")
    bbb = provider.get_window("2025-01-07", asset="BBB")
    assert len(bbb) == 5
    assert (bbb["ticker"] == "BBB").all()
