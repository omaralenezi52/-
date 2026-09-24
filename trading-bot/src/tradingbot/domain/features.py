"""
محرك بناء المعلومات (Feature Engineering) — حساب المؤشرات الفنية.

مبدأ الدقة: المؤشرات محسوبة يدوياً بـ pandas/numpy (لا صندوق أسود خارجي)،
فتملك كل سطر، ونفس الدالة تُستخدم في الاختبار التاريخي والتنفيذ الحي
→ تطابق مضمون (لا فجوة Backtest-Live).

⚠️ منع Look-ahead: الحسابات تُقرأ من الشمعة *المغلقة* الأخيرة. مرّر
drop_forming=True إذا كان آخر صف شمعة غير مكتملة (تداول حي).
"""
from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from .decision import Evidence
from .models import Side

# أسماء الأعمدة المتوقعة (OHLCV)
REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """RSI بطريقة Wilder (المعيار الصناعي)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # متوسط Wilder: alpha = 1/length
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100)  # لا خسائر ⇒ RSI = 100


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """متوسط المدى الحقيقي (ATR) بطريقة Wilder — مقياس التقلب."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def validate_ohlcv(df: pd.DataFrame, min_rows: int = 50) -> None:
    """يتحقق من سلامة البيانات قبل الحساب (دقة تبدأ من بيانات نظيفة)."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"أعمدة ناقصة في البيانات: {missing}")
    if len(df) < min_rows:
        raise ValueError(f"عدد الشموع {len(df)} أقل من الحد الأدنى {min_rows}")
    if df[list(REQUIRED_COLUMNS)].isnull().any().any():
        raise ValueError("توجد قيم مفقودة (NaN) في البيانات الخام")


def compute_features(df: pd.DataFrame, drop_forming: bool = False) -> dict:
    """
    يحسب كل المؤشرات ويُرجع قيم الشمعة المغلقة الأخيرة كقاموس.
    القاموس نفسه يُمرَّر إلى DecisionEngine و LLM.
    """
    validate_ohlcv(df)
    data = df.iloc[:-1] if drop_forming else df  # استبعاد الشمعة غير المكتملة

    close = data["close"]
    ema_fast = _ema(close, 20)
    ema_slow = _ema(close, 50)
    ema_trend = _ema(close, 200)
    rsi = _rsi(close, 14)
    atr = _atr(data, 14)
    vol_sma = data["volume"].rolling(20).mean()

    last = data.iloc[-1]
    return {
        "close": float(last["close"]),
        "ema_fast": float(ema_fast.iloc[-1]),
        "ema_slow": float(ema_slow.iloc[-1]),
        "ema_trend": float(ema_trend.iloc[-1]),
        "rsi": float(rsi.iloc[-1]),
        "atr": float(atr.iloc[-1]),
        "volume": float(last["volume"]),
        "volume_sma": float(vol_sma.iloc[-1]) if not np.isnan(vol_sma.iloc[-1]) else 0.0,
        # ADX تقريبي عبر ميل الاتجاه (مبسّط لكشف النظام)
        "adx": _trend_strength(ema_fast, ema_slow),
    }


def _trend_strength(ema_fast: pd.Series, ema_slow: pd.Series) -> float:
    """مقياس مبسّط لقوة الاتجاه (بديل خفيف عن ADX)."""
    spread = (ema_fast - ema_slow).abs()
    ref = ema_slow.abs().replace(0, np.nan)
    pct = float((spread.iloc[-1] / ref.iloc[-1]) * 100) if ref.iloc[-1] else 0.0
    # نحوّله لمقياس شبيه بـ ADX: انتشار كبير ⇒ اتجاه قوي
    return min(pct * 10, 100.0)


def features_to_evidence(features: dict) -> list[Evidence]:
    """
    يحوّل المؤشرات الرقمية إلى أدلة (Evidence) لمحرك التوافق.
    كل دليل حتمي وقابل للتفسير — لا عشوائية.
    """
    evidences: list[Evidence] = []
    close = features["close"]

    # دليل الاتجاه: تقاطع المتوسطات
    if features["ema_fast"] > features["ema_slow"]:
        evidences.append(Evidence("trend", Side.BUY, 0.35,
                                  f"EMA20 ({features['ema_fast']:.2f}) > EMA50"))
    else:
        evidences.append(Evidence("trend", Side.SELL, 0.35,
                                  f"EMA20 ({features['ema_fast']:.2f}) < EMA50"))

    # دليل الاتجاه طويل المدى (EMA200)
    if close > features["ema_trend"]:
        evidences.append(Evidence("long_trend", Side.BUY, 0.20, "السعر فوق EMA200"))
    else:
        evidences.append(Evidence("long_trend", Side.SELL, 0.20, "السعر تحت EMA200"))

    # دليل الزخم: RSI (نتجنّب الدخول في مناطق التشبع الخطرة)
    rsi = features["rsi"]
    if 40 <= rsi <= 65:
        evidences.append(Evidence("momentum", Side.BUY, 0.25, f"RSI صحي {rsi:.1f}"))
    elif rsi > 75:
        evidences.append(Evidence("momentum", Side.SELL, 0.25, f"RSI تشبع شرائي {rsi:.1f}"))
    elif rsi < 25:
        evidences.append(Evidence("momentum", Side.BUY, 0.25, f"RSI تشبع بيعي {rsi:.1f}"))

    # دليل الحجم: تأكيد الحركة
    if features["volume_sma"] > 0 and features["volume"] > features["volume_sma"] * 1.2:
        side = Side.BUY if features["ema_fast"] > features["ema_slow"] else Side.SELL
        evidences.append(Evidence("volume", side, 0.20, "حجم أعلى من المتوسط (تأكيد)"))

    return evidences


def atr_from_features(features: dict) -> Decimal:
    """يُرجع ATR كـ Decimal لاستخدامه في اشتقاق مستويات الوقف بدقة."""
    return Decimal(str(features["atr"]))
