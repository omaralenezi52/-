"""
التجميع الرئيسي (Wiring) — يبني النظام كاملاً من الإعدادات.

هذا هو المكان الذي "تنحط" فيه بياناتك: بمجرد ضبط .env (WEBHOOK_SECRET،
ANTHROPIC_API_KEY، بيانات IBKR، توكن تليجرام) يلتقطها هذا الملف تلقائياً
ويربط كل الطبقات. لا حاجة لتعديل أي كود آخر.

التدفق عند وصول إشارة:
  Webhook → build_signal → run_pipeline_with_analyst → Telegram (توصية)
          → التنفيذ عبر المنصة (حسب TradeMode والمنصة المختارة)
"""
from __future__ import annotations

import logging
import uuid

from .adapters.alpaca import AlpacaAdapter
from .adapters.base import BrokerAdapter, NotSupportedError
from .adapters.derayah import DerayahAdapter
from .adapters.ibkr import IBKRAdapter
from .adapters.paper import PaperBroker
from .agent.analyst import build_analyst
from .config import Settings
from .domain.decision import DecisionEngine
from .domain.features import features_to_evidence
from .domain.models import Decision, Signal, TradeMode
from .domain.risk import RiskEngine, RiskLimits
from .notify.telegram import TelegramNotifier
from .pipeline import run_pipeline_with_analyst

logger = logging.getLogger("tradingbot.app")


def build_broker(settings: Settings) -> BrokerAdapter:
    """يختار المنصة حسب الإعداد. IBKR يتصل عند البناء إذا اختير."""
    if settings.broker == "alpaca":
        return AlpacaAdapter(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=settings.alpaca_paper,
        )
    if settings.broker == "ibkr":
        adapter = IBKRAdapter(
            host=settings.ibkr_host,
            port=settings.ibkr_port,
            client_id=settings.ibkr_client_id,
            account=settings.ibkr_account,
        )
        adapter.connect()  # يتطلب TWS/Gateway مشغّلاً وبياناتك في .env
        return adapter
    if settings.broker == "derayah":
        # تُدخل قيم الحساب يدوياً لأن لا API تنفيذ لدراية
        from decimal import Decimal
        return DerayahAdapter(equity=Decimal("0"), cash=Decimal("0"))
    return PaperBroker()


class TradingApp:
    """يجمّع المحلل والمحرك والمخاطر والمنصة والإشعارات في نقطة واحدة."""

    def __init__(self, settings: Settings, broker: BrokerAdapter | None = None) -> None:
        self.settings = settings
        self.decision_engine = DecisionEngine(min_agreeing=3)
        self.risk_engine = RiskEngine(RiskLimits())
        self.analyst = build_analyst(settings.anthropic_api_key, settings.analyst_model)
        self.notifier = TelegramNotifier(settings.telegram_token, settings.telegram_chat_id)
        self.broker = broker or build_broker(settings)
        self.paused = False               # /pause من تليجرام
        self._pending: dict = {}          # توصيات تنتظر موافقة SEMI_AUTO
        self.last_read: dict = {}         # آخر قراءة سوق لكل رمز (للتشخيص)
        self.live_loop = None             # يُضبط في main لتفعيل /diag
        # دفتر الصفقات (الذاكرة الدائمة) — لا يُسقِط النظام لو فشل
        try:
            from .journal.trade_journal import TradeJournal
            self.journal = TradeJournal(database_url=settings.database_url)
            logger.info("دفتر الصفقات: %s", "Postgres" if self.journal.is_postgres else "SQLite")
        except Exception:
            logger.exception("تعذّر تهيئة دفتر الصفقات — المتابعة بدونه")
            self.journal = None

    def handle_signal(self, signal: Signal) -> None:
        """المعالج المربوط بالـ Webhook: يحلّل، يوصي، ثم ينفّذ حسب الوضع."""
        features = signal.indicators or {}
        evidences = features_to_evidence(features) if features else []

        account = self.broker.get_account_state()
        rec = run_pipeline_with_analyst(
            signal=signal,
            evidences=evidences,
            account=account,
            decision_engine=self.decision_engine,
            risk_engine=self.risk_engine,
            analyst=self.analyst,
            features=features,
        )

        # نسجّل آخر قراءة لكل رمز (دليل أنه يقرأ السوق — يظهر في /diag)
        from datetime import datetime, timezone
        self.last_read[signal.symbol] = {
            "price": features.get("close"),
            "rsi": features.get("rsi"),
            "regime": rec.regime.value,
            "decision": rec.decision.value,
            "confidence": rec.confidence,
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        }

        # نسجّل كل توصية في الذاكرة الدائمة
        if self.journal is not None:
            try:
                self.journal.log_recommendation(rec)
            except Exception:
                logger.exception("فشل تسجيل التوصية في الدفتر")

        if self.paused:
            logger.info("البوت موقوف مؤقتاً (/pause) — تجاهل %s", signal.symbol)
            return

        if not rec.is_actionable:
            self.notifier.send(rec)   # توصية انتظار/رفض بلا أزرار
            return

        if self.settings.mode == TradeMode.FULL_AUTO:
            self.notifier.send(rec)
            self._execute(rec)
        elif self.settings.mode == TradeMode.SEMI_AUTO:
            # نخزّن التوصية ونرسلها بأزرار موافقة
            approval_id = uuid.uuid4().hex[:10]
            self._pending[approval_id] = rec
            self.notifier.send(rec, approval_id=approval_id)
            logger.info("توصية %s بانتظار موافقتك في تليجرام", rec.symbol)
        else:  # ADVISOR
            self.notifier.send(rec)

    def approve(self, approval_id: str) -> str:
        """ينفّذ توصية معلّقة بعد موافقة المستخدم (من زر تليجرام)."""
        rec = self._pending.pop(approval_id, None)
        if rec is None:
            return "⚠️ التوصية لم تعد متاحة (نُفّذت أو انتهت)."
        self._execute(rec)
        return f"✅ نُفّذت: {rec.decision.value} {rec.symbol}"

    def reject(self, approval_id: str) -> str:
        """يتجاهل توصية معلّقة."""
        rec = self._pending.pop(approval_id, None)
        return "❌ تم التجاهل." if rec else "⚠️ التوصية لم تعد متاحة."

    def status_text(self) -> str:
        """ملخص حالة البوت لأمر /status (لا يفشل حتى لو المنصة غير متاحة)."""
        head = (
            f"🤖 حالة البوت\n"
            f"الوضع: {self.settings.mode.value}"
            f"{' (موقوف)' if self.paused else ''}\n"
            f"المنصة: {self.broker.name}\n"
        )
        try:
            acc = self.broker.get_account_state()
            body = (
                f"الرصيد: {acc.equity} | النقد: {acc.cash_available}\n"
                f"الصفقات المفتوحة: {acc.open_positions}\n"
            )
        except Exception as exc:  # مفاتيح غلط / المنصة غير متاحة
            body = (
                "⚠️ تعذّر الاتصال بالمنصة — تحقّق من مفاتيح Alpaca في الإعدادات.\n"
                f"({str(exc)[:80]})\n"
            )
        return head + body + f"توصيات معلّقة: {len(self._pending)}"

    def stats_text(self) -> str:
        """ملخص الأداء من دفتر الصفقات (أمر /stats)."""
        if self.journal is None:
            return "📒 الدفتر غير مُفعّل."
        try:
            s = self.journal.stats()
        except Exception as exc:
            return f"⚠️ تعذّر قراءة الدفتر: {str(exc)[:80]}"
        return (
            f"📒 أداء البوت (من الذاكرة الدائمة)\n"
            f"إجمالي التوصيات: {s['total_recommendations']}\n"
            f"صفقات مفتوحة: {s['open_trades']}\n"
            f"صفقات مغلقة: {s['closed_trades']}\n"
            f"نسبة النجاح: {s['win_rate']*100:.0f}% ({s['wins']}/{s['closed_trades']})\n"
            f"صافي الربح/الخسارة: {s['total_pnl']}"
        )

    def diagnose_text(self) -> str:
        """يجبر دورة قراءة فورية ويعرض ما قرأه البوت من السوق (أمر /diag)."""
        if self.live_loop is not None:
            try:
                self.live_loop.run_cycle()
            except Exception as exc:
                return f"⚠️ فشل فحص السوق: {str(exc)[:100]}"

        if not self.last_read:
            return ("🔍 لم تُقرأ بيانات بعد.\n"
                    "قد يكون السوق مغلقاً أو لم تكتمل أول دورة.")

        lines = ["🔍 آخر قراءة للسوق:"]
        for sym, d in self.last_read.items():
            lines.append(
                f"• {sym}: السعر {d['price']} | RSI {d['rsi']:.0f} | "
                f"{d['regime']} → {d['decision']} ({d['confidence']:.0%}) [{d['time']}]"
            )
        return "\n".join(lines)

    def _execute(self, rec) -> None:
        client_order_id = f"{rec.symbol}-{uuid.uuid4().hex[:12]}"  # مفتاح تفرّد
        try:
            result = self.broker.place_bracket_order(rec.plan, client_order_id)
            logger.info("نُفّذت الصفقة: %s (%s)", result.order_id, result.status)
            if self.journal is not None:
                try:
                    self.journal.log_trade(rec, client_order_id)
                except Exception:
                    logger.exception("فشل تسجيل الصفقة في الدفتر")
        except NotSupportedError as exc:
            logger.warning("المنصة لا تدعم التنفيذ الآلي: %s — إشعار فقط", exc)
        except Exception:
            logger.exception("فشل تنفيذ الصفقة عبر المنصة")
