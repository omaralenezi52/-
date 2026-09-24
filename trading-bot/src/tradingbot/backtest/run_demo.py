"""
تشغيل تجريبي للباك تيست على بيانات اصطناعية أو ملف CSV.

الاستخدام:
    python -m tradingbot.backtest.run_demo                 # بيانات اصطناعية
    python -m tradingbot.backtest.run_demo path/to/ohlcv.csv

صيغة CSV المتوقعة: أعمدة open,high,low,close,volume (والأحدث في الأسفل).
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from .engine import Backtester


def _synthetic(n: int = 500, seed: int = 3) -> pd.DataFrame:
    """بيانات اصطناعية باتجاه صاعد مع تذبذب — لأغراض العرض فقط."""
    rng = np.random.default_rng(seed)
    base = np.linspace(100, 180, n) + np.sin(np.linspace(0, 20, n)) * 5
    close = base + rng.normal(0, 1.2, n)
    high = close + np.abs(rng.normal(0, 1.0, n)) + 0.5
    low = close - np.abs(rng.normal(0, 1.0, n)) - 0.5
    open_ = close - rng.normal(0, 0.4, n)
    volume = rng.integers(1000, 8000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


def main() -> None:
    if len(sys.argv) > 1:
        df = pd.read_csv(sys.argv[1])
        print(f"حُمّلت {len(df)} شمعة من {sys.argv[1]}")
    else:
        df = _synthetic()
        print("تشغيل على بيانات اصطناعية (للعرض فقط — ليست نتيجة حقيقية)")

    result = Backtester(warmup=200).run(df)
    print(result.summary())


if __name__ == "__main__":
    main()
