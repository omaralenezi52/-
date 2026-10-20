"""اختبار التحقق المتدرّج الأمامي."""
import numpy as np
import pandas as pd

from tradingbot.backtest.walkforward import walk_forward


def make_df(n=1200, seed=11):
    rng = np.random.default_rng(seed)
    base = np.linspace(100, 220, n) + np.sin(np.linspace(0, 40, n)) * 8
    close = base + rng.normal(0, 1.3, n)
    high = close + np.abs(rng.normal(0, 1, n)) + 0.4
    low = close - np.abs(rng.normal(0, 1, n)) - 0.4
    return pd.DataFrame({
        "open": close - rng.normal(0, 0.3, n), "high": high, "low": low,
        "close": close, "volume": rng.integers(2000, 9000, n).astype(float),
    })


def test_walk_forward_produces_windows():
    report = walk_forward(make_df(), n_windows=4, warmup=200)
    assert len(report.windows) >= 1
    assert all(w.bars > 0 for w in report.windows)


def test_walk_forward_consistency_in_range():
    report = walk_forward(make_df(), n_windows=4, warmup=200)
    assert 0.0 <= report.consistency <= 1.0
    assert isinstance(report.summary(), str)


def test_walk_forward_rejects_small_data():
    import pytest
    with pytest.raises(ValueError):
        walk_forward(make_df(n=210), n_windows=4, warmup=200)
