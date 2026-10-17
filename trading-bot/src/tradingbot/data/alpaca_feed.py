"""
جلب بيانات الشموع (OHLCV) من Alpaca — يغذّي محرك المؤشرات.

يُرجع DataFrame بأعمدة open/high/low/close/volume جاهزة لـ compute_features.
المفاتيح تُقرأ من البيئة وقت التشغيل.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("tradingbot.data.alpaca")

# خريطة الأطر الزمنية النصّية إلى وحدات Alpaca (تُحلّ كسولاً عند الاستخدام)
_TF_MAP = {"1m": (1, "Minute"), "5m": (5, "Minute"), "15m": (15, "Minute"),
           "1h": (1, "Hour"), "1d": (1, "Day")}


class AlpacaDataFeed:
    def __init__(self, api_key: str = "", secret_key: str = "", client=None) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self._client = client

    def _get_client(self):
        if self._client is None:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("ثبّت alpaca-py: pip install alpaca-py") from exc
            self._client = StockHistoricalDataClient(self.api_key, self.secret_key)
        return self._client

    def get_candles(self, symbol: str, timeframe: str = "1h", limit: int = 300):
        """
        يجلب آخر `limit` شمعة. يُرجع pandas.DataFrame
        بأعمدة: open, high, low, close, volume (مرتّبة زمنياً تصاعدياً).
        """
        import pandas as pd
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        if timeframe not in _TF_MAP:
            raise ValueError(f"إطار زمني غير مدعوم: {timeframe}")
        amount, unit = _TF_MAP[timeframe]
        tf = TimeFrame(amount, getattr(TimeFrameUnit, unit))

        client = self._get_client()
        req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, limit=limit)
        bars = client.get_stock_bars(req)

        df = bars.df
        if df is None or df.empty:
            raise ValueError(f"لا توجد بيانات لـ {symbol}")
        # عند رمز واحد يكون الفهرس متعدد المستويات (symbol, timestamp)
        if "symbol" in df.index.names:
            df = df.xs(symbol, level="symbol")
        df = df.reset_index()
        return pd.DataFrame({
            "open": df["open"].astype(float),
            "high": df["high"].astype(float),
            "low": df["low"].astype(float),
            "close": df["close"].astype(float),
            "volume": df["volume"].astype(float),
        })
