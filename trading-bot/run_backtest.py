"""
تشغيل الباك تيست على بيانات حقيقية — شغّله على جهازك (شبكتك غير مقيّدة).

أمثلة:
    # من Yahoo Finance (مجاني، بلا مفاتيح)
    python run_backtest.py AAPL --start 2022-01-01 --end 2024-12-31

    # من ملف CSV بأعمدة open,high,low,close,volume
    python run_backtest.py --csv data/aapl.csv

ثبّت أولاً:  pip install yfinance
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "src")

from tradingbot.backtest.engine import Backtester


def load_yf(symbol: str, start: str, end: str, interval: str):
    import yfinance as yf
    df = yf.download(symbol, start=start, end=end, interval=interval,
                     progress=False, auto_adjust=True)
    if df.empty:
        raise SystemExit(f"لا توجد بيانات لـ {symbol}")
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
    return df[["open", "high", "low", "close", "volume"]].reset_index(drop=True)


def load_csv(path: str):
    import pandas as pd
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    return df[["open", "high", "low", "close", "volume"]]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("symbol", nargs="?", default="AAPL")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--interval", default="1d")
    p.add_argument("--csv")
    p.add_argument("--warmup", type=int, default=200)
    args = p.parse_args()

    df = load_csv(args.csv) if args.csv else load_yf(args.symbol, args.start, args.end, args.interval)
    print(f"حُمّلت {len(df)} شمعة")
    result = Backtester(warmup=args.warmup).run(df)
    print(result.summary())


if __name__ == "__main__":
    main()
