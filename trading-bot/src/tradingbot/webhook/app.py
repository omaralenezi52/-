"""
مستقبِل Webhook آمن (FastAPI) لإشارات TradingView.

نقاط الخطر المُغلقة هنا (مطابقة لتفضيلات الأمان):
1. توكن سري إلزامي — يُقارن بطريقة ثابتة الزمن (secrets.compare_digest)
   لمنع هجمات التوقيت، ويرفض أي إشارة مزيّفة.
2. التحقق الصارم من المدخلات عبر Pydantic — لا نثق بأي JSON قادم
   (حماية من الحقن والبيانات المشوّهة).
3. تحويل الأرقام إلى Decimal لتجنّب أخطاء float المالية.
4. إدارة أخطاء واضحة + تسجيل (logging) لكل إشارة للتتبع.

يُشغّل خلف HTTPS دائماً (لا HTTP) — أنهِ TLS عبر reverse proxy في الإنتاج.
"""
from __future__ import annotations

import logging
import secrets
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from ..config import Settings
from ..domain.models import Side, Signal

logger = logging.getLogger("tradingbot.webhook")


class WebhookPayload(BaseModel):
    """
    مخطّط الإشارة الواردة. صارم عمداً — أي حقل ناقص أو نوع خاطئ يُرفض.
    """
    secret: str = Field(..., min_length=8)
    symbol: str = Field(..., min_length=1, max_length=20)
    action: str = Field(..., description="BUY أو SELL")
    price: Decimal = Field(..., gt=0)
    source: str = Field(default="tradingview", max_length=40)
    timeframe: str = Field(default="1h", max_length=10)
    indicators: dict = Field(default_factory=dict)

    @field_validator("action")
    @classmethod
    def _validate_action(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("BUY", "SELL"):
            raise ValueError("action يجب أن تكون BUY أو SELL")
        return v

    @field_validator("symbol")
    @classmethod
    def _clean_symbol(cls, v: str) -> str:
        # نحصر الرمز في أحرف/أرقام آمنة لمنع أي حقن
        cleaned = v.strip().upper()
        if not all(c.isalnum() or c in "/._-" for c in cleaned):
            raise ValueError("رمز غير صالح")
        return cleaned


def create_app(settings: Settings, on_signal=None) -> FastAPI:
    """
    ينشئ تطبيق FastAPI. on_signal: دالة تُستدعى بالإشارة المعتمدة
    (تربطها لاحقاً بمحرك القرار/الـ Pipeline).
    """
    app = FastAPI(title="Trading Bot Webhook", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/webhook/tradingview")
    def receive(payload: WebhookPayload) -> dict:
        # --- التحقق من التوكن بمقارنة ثابتة الزمن ---
        if not secrets.compare_digest(payload.secret, settings.webhook_secret):
            logger.warning("رُفضت إشارة: توكن غير صحيح (symbol=%s)", payload.symbol)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="توكن غير صالح",
            )

        try:
            signal = Signal(
                symbol=payload.symbol,
                side=Side(payload.action),
                price=payload.price,
                source=payload.source,
                indicators=payload.indicators,
                timeframe=payload.timeframe,
            )
        except (ValueError, InvalidOperation) as exc:
            logger.error("إشارة غير صالحة: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"إشارة غير صالحة: {exc}",
            )

        logger.info("إشارة مقبولة: %s %s @ %s", signal.side.value, signal.symbol, signal.price)

        if on_signal is not None:
            try:
                on_signal(signal)
            except Exception:  # لا نُسقط الطلب بسبب خطأ في المعالجة اللاحقة
                logger.exception("فشل في معالجة الإشارة بعد الاستقبال")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="خطأ داخلي أثناء معالجة الإشارة",
                )

        return {"status": "accepted", "symbol": signal.symbol, "action": signal.side.value}

    return app
