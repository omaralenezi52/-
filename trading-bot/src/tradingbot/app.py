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

        # التوصية تُرسل دائماً على تليجرام (في كل الأوضاع)
        self.notifier.send(rec)

        # التنفيذ فقط في FULL_AUTO وعند توصية قابلة للتنفيذ
        if self.settings.mode == TradeMode.FULL_AUTO and rec.is_actionable:
            self._execute(rec)
        elif rec.is_actionable:
            logger.info("توصية %s جاهزة — بانتظار التنفيذ اليدوي/الموافقة (%s)",
                        rec.decision.value, self.settings.mode.value)

    def _execute(self, rec) -> None:
        client_order_id = f"{rec.symbol}-{uuid.uuid4().hex[:12]}"  # مفتاح تفرّد
        try:
            result = self.broker.place_bracket_order(rec.plan, client_order_id)
            logger.info("نُفّذت الصفقة: %s (%s)", result.order_id, result.status)
        except NotSupportedError as exc:
            logger.warning("المنصة لا تدعم التنفيذ الآلي: %s — إشعار فقط", exc)
        except Exception:
            logger.exception("فشل تنفيذ الصفقة عبر المنصة")
