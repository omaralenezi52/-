"""
نقطة التشغيل — تربط الـ Webhook بالتطبيق الكامل.

    uvicorn tradingbot.serve:app --host 0.0.0.0 --port 8000

تقرأ الإعدادات من .env، تبني TradingApp، وتوجّه كل إشارة واردة إلى
معالجها. شغّلها خلف HTTPS في الإنتاج (reverse proxy).
"""
from __future__ import annotations

import logging

from .app import TradingApp
from .config import Settings
from .webhook.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = Settings.from_env()
_trading_app = TradingApp(settings)
app = create_app(settings, on_signal=_trading_app.handle_signal)
