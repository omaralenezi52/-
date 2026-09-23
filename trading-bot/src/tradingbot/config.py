"""
إعدادات النظام — تُقرأ من متغيّرات البيئة (.env)، لا تُكتب في الكود أبداً.

قاعدة أمنية: لا مفاتيح ولا توكنات في المستودع. استخدم .env محلياً
(مضاف لـ .gitignore) وأسرار المنصة في الإنتاج.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .domain.models import TradeMode


@dataclass(frozen=True)
class Settings:
    # التوكن السري الذي يجب أن يحمله كل طلب Webhook (يمنع الإشارات المزيّفة)
    webhook_secret: str
    # توكن بوت تليجرام ومعرّف المحادثة المصرّح له
    telegram_token: str = ""
    telegram_chat_id: str = ""
    # مفتاح الـ LLM
    anthropic_api_key: str = ""
    # وضع التشغيل الافتراضي — الأكثر أماناً
    mode: TradeMode = TradeMode.ADVISOR

    @staticmethod
    def from_env() -> "Settings":
        secret = os.environ.get("WEBHOOK_SECRET", "").strip()
        if not secret:
            raise RuntimeError(
                "WEBHOOK_SECRET مفقود — عيّنه في .env قبل التشغيل (إلزامي للأمان)"
            )
        mode_raw = os.environ.get("TRADE_MODE", "ADVISOR").strip().upper()
        try:
            mode = TradeMode(mode_raw)
        except ValueError:
            mode = TradeMode.ADVISOR
        return Settings(
            webhook_secret=secret,
            telegram_token=os.environ.get("TELEGRAM_TOKEN", "").strip(),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            mode=mode,
        )
