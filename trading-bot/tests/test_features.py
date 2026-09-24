"""اختبارات محرك المؤشرات — التحقق من صحة الحسابات ومنع Look-ahead."""
import numpy as np
import pandas as pd
import pytest

from tradingbot.domain.features import (
    compute_features,
    features_to_evidence,
    validate_ohlcv,
)
from tradingbot.domain.models import Side


def make_df(n=120, trend="up", seed=42):
    """يولّد بيانات OHLCV اصطناعية باتجاه محدد."""
    rng = np.random.default_rng(seed)
    if trend == "up":
        base = np.linspace(100, 130, n)
    else:
        base = np.linspace(130, 100, n)
    noise = rng.normal(0, 0.5, n)
    close = base + noise
    high = close + np.abs(rng.normal(0, 0.4, n))
    low = close - np.abs(rng.normal(0, 0.4, n))
    open_ = close - rng.normal(0, 0.2, n)
    volume = rng.integers(1000, 5000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


def test_validate_rejects_missing_columns():
    df = pd.DataFrame({"close": [1, 2, 3]})
    with pytest.raises(ValueError, match="ناقصة"):
        validate_ohlcv(df)


def test_validate_rejects_too_few_rows():
    with pytest.raises(ValueError, match="أقل من"):
        validate_ohlcv(make_df(n=10))


def test_compute_features_returns_expected_keys():
    f = compute_features(make_df())
    for key in ("close", "ema_fast", "ema_slow", "rsi", "atr", "volume"):
        assert key in f
    assert 0 <= f["rsi"] <= 100
    assert f["atr"] > 0


def test_uptrend_has_fast_above_slow():
    f = compute_features(make_df(trend="up"))
    assert f["ema_fast"] > f["ema_slow"]


def test_downtrend_has_fast_below_slow():
    f = compute_features(make_df(trend="down"))
    assert f["ema_fast"] < f["ema_slow"]


def test_drop_forming_excludes_last_candle():
    """منع Look-ahead: النتيجة مع drop_forming تعكس الشمعة قبل الأخيرة."""
    df = make_df()
    f_all = compute_features(df, drop_forming=False)
    f_closed = compute_features(df, drop_forming=True)
    # القيمتان مختلفتان لأن الأخيرة استُبعدت
    assert f_all["close"] != f_closed["close"]


def test_features_to_evidence_uptrend_favors_buy():
    f = compute_features(make_df(trend="up"))
    evs = features_to_evidence(f)
    buy_weight = sum(e.weight for e in evs if e.side == Side.BUY)
    sell_weight = sum(e.weight for e in evs if e.side == Side.SELL)
    assert buy_weight > sell_weight


def test_rsi_calculation_reasonable_for_strong_uptrend():
    # اتجاه صاعد قوي ⇒ RSI مرتفع
    f = compute_features(make_df(trend="up", seed=1))
    assert f["rsi"] > 50
