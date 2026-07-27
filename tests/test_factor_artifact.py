import numpy as np
import pandas as pd

from finvl.factors.library import FactorLibrary


def test_frozen_manifest_preserves_all_157_records_and_finite_outputs():
    n = 100
    close = np.linspace(100, 130, n) + np.sin(np.arange(n))
    frame = pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.linspace(1_000_000, 2_000_000, n),
        }
    )
    library = FactorLibrary()
    evolved = [factor for factor in library.factors.values() if factor.category == "evolved"]
    assert len(evolved) == 157
    values = library.compute_all(frame)
    assert np.isfinite(values.to_numpy()).all()
