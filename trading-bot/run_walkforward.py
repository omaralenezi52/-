"""
تشغيل التحقق المتدرّج الأمامي على بيانات حقيقية (على جهازك).

    pip install yfinance
    python run_walkforward.py AAPL --start 2020-01-01 --end 2024-12-31

يكشف هل أداء الاستراتيجية ثابت عبر فترات مختلفة (غير محفوظ Overfitting).
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "src")

from tradingbot.backtest.walkforward import walk_forward


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("symbol", nargs="?", default="AAPL")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--windows", type=int, default=5)
    p.add_argument("--warmup", type=int, default=200)
    args = p.parse_args()

    import yfinance as yf
    df = yf.download(args.symbol, start=args.start, end=args.end,
                     interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        raise SystemExit("لا توجد بيانات")
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].reset_index(drop=True)

    print(f"حُمّلت {len(df)} شمعة")
    report = walk_forward(df, n_windows=args.windows, warmup=args.warmup)
    print(report.summary())


if __name__ == "__main__":
    main()
