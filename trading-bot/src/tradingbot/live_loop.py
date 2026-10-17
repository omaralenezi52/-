"""
الحلقة الحية (Live Loop) — تربط كل الطبقات في دورة ذاتية التشغيل.

كل دورة (عند إغلاق الشمعة):
  1. تجلب الشموع من مزوّد البيانات.
  2. تحسب المؤشرات (على الشمعة المغلقة — منع Look-ahead).
  3. تبني إشارة وتمرّرها عبر الـ Pipeline (توافق → محلل → مخاطر).
  4. توصية → تليجرام، وتنفيذ حسب الوضع.

هذا ما يحوّل النظام من "ينتظر إشارة" إلى "يراقب ويقرر لحاله".
"""
from __future__ import annotations

import logging
from decimal import Decimal

from .app import TradingApp
from .domain.features import compute_features
from .domain.models import Side, Signal

logger = logging.getLogger("tradingbot.live")


class LiveLoop:
    def __init__(self, app: TradingApp, data_feed, symbols: list[str],
                 timeframe: str = "1h") -> None:
        self.app = app
        self.data_feed = data_feed
        self.symbols = symbols
        self.timeframe = timeframe

    def run_once(self, symbol: str) -> None:
        """دورة واحدة لرمز واحد: جلب → حساب → قرار → توصية/تنفيذ."""
        try:
            df = self.data_feed.get_candles(symbol, self.timeframe, limit=300)
        except Exception:
            logger.exception("فشل جلب بيانات %s — تخطّي هذه الدورة", symbol)
            return

        try:
            # drop_forming=True: نحسب على الشمعة المغلقة الأخيرة فقط
            features = compute_features(df, drop_forming=True)
        except ValueError as exc:
            logger.warning("بيانات غير كافية لـ %s: %s", symbol, exc)
            return

        # اتجاه الإشارة المرشّح من غلبة الأدلة (نترك DecisionEngine يؤكد/يرفض)
        side = Side.BUY if features["ema_fast"] > features["ema_slow"] else Side.SELL
        signal = Signal(
            symbol=symbol, side=side,
            price=Decimal(str(features["close"])),
            indicators=features, timeframe=self.timeframe,
            source="live_loop",
        )
        # المعالج نفسه المربوط بالـ Webhook — نفس المنطق بالضبط
        self.app.handle_signal(signal)

    def run_cycle(self) -> None:
        """دورة كاملة على كل الرموز المراقَبة."""
        for symbol in self.symbols:
            logger.info("فحص %s...", symbol)
            self.run_once(symbol)
