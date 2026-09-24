"""
إعدادات النظام — تُقرأ من متغيّرات البيئة (.env)، لا تُكتب في الكود أبداً.

قاعدة أمنية: لا مفاتيح ولا توكنات في المستودع. تحط بياناتك في .env
(المضاف لـ .gitignore) وأسرار المنصة في الإنتاج — والكود يلتقطها تلقائياً.
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
    # مفتاح الـ LLM + النموذج
    anthropic_api_key: str = ""
    analyst_model: str = "claude-opus-5"
    # إعدادات Interactive Brokers (تحط بياناتك هنا عبر .env)
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497          # 7497 = Paper، 7496 = Live
    ibkr_client_id: int = 1
    ibkr_account: str = ""
    broker: str = "paper"          # paper | ibkr | derayah
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

        def _int(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, default))
            except (TypeError, ValueError):
                return default

        return Settings(
            webhook_secret=secret,
            telegram_token=os.environ.get("TELEGRAM_TOKEN", "").strip(),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            analyst_model=os.environ.get("ANALYST_MODEL", "claude-opus-5").strip(),
            ibkr_host=os.environ.get("IBKR_HOST", "127.0.0.1").strip(),
            ibkr_port=_int("IBKR_PORT", 7497),
            ibkr_client_id=_int("IBKR_CLIENT_ID", 1),
            ibkr_account=os.environ.get("IBKR_ACCOUNT", "").strip(),
            broker=os.environ.get("BROKER", "paper").strip().lower(),
            mode=mode,
        )
