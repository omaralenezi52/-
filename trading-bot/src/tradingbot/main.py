"""
نقطة التشغيل الموحّدة (All-in-one) — تشغّل كل شيء في عملية واحدة.

مصمّمة لمنصات النشر (CranL/Railway/…) التي تشغّل أمراً افتراضياً واحداً:
  1. بوت تليجرام التفاعلي (خيط) — يرد على الأزرار والأوامر.
  2. الحلقة الحية (خيط) — تراقب الرموز وتقرر عند إغلاق الشمعة.
  3. خادم الـ Webhook (الخيط الرئيسي) — يفتح المنفذ الذي تتطلّبه المنصة.

الرموز من متغيّر البيئة SYMBOLS (مفصولة بفواصل)، والمنفذ من PORT.
"""
from __future__ import annotations

import logging
import os
import threading
import time

import schedule
import uvicorn

from .app import TradingApp
from .config import Settings
from .data.alpaca_feed import AlpacaDataFeed
from .live_loop import LiveLoop
from .notify.telegram_bot import TelegramBot
from .webhook.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tradingbot.main")


def _start_telegram(app: TradingApp, settings: Settings) -> None:
    if not (settings.telegram_token and settings.telegram_chat_id):
        logger.info("تليجرام غير مُهيّأ — تخطّي البوت التفاعلي")
        return
    bot = TelegramBot(app, settings.telegram_token, settings.telegram_chat_id)
    threading.Thread(target=bot.run, daemon=True).start()
    logger.info("بوت تليجرام التفاعلي يعمل")
    # رسالة إقلاع ليعرف المستخدم أن البوت حيّ
    app.notifier.send_text("🚀 البوت يعمل الآن. أرسل /status للحالة.")


def _start_live_loop(app: TradingApp, settings: Settings, symbols: list[str]) -> None:
    feed = AlpacaDataFeed(settings.alpaca_api_key, settings.alpaca_secret_key)
    loop = LiveLoop(app, feed, symbols, timeframe=os.environ.get("TIMEFRAME", "1h"))
    app.live_loop = loop   # يتيح أمر /diag في تليجرام

    def worker():
        schedule.every().hour.at(":01").do(loop.run_cycle)
        try:
            loop.run_cycle()  # دورة فورية عند الإقلاع
        except Exception:
            logger.exception("فشل الدورة الأولى للحلقة الحية")
        while True:
            schedule.run_pending()
            time.sleep(5)

    threading.Thread(target=worker, daemon=True).start()
    logger.info("الحلقة الحية تعمل | الرموز=%s", symbols)


def main() -> None:
    settings = Settings.from_env()
    app = TradingApp(settings)

    symbols = [s.strip().upper() for s in os.environ.get("SYMBOLS", "AAPL").split(",") if s.strip()]
    port = int(os.environ.get("PORT", "8000"))

    logger.info("إقلاع النظام | الوضع=%s | المنصة=%s | المنفذ=%s",
                settings.mode.value, settings.broker, port)

    _start_telegram(app, settings)
    _start_live_loop(app, settings, symbols)

    # خادم الـ Webhook في الخيط الرئيسي (يفتح المنفذ للمنصة)
    webhook_app = create_app(settings, on_signal=app.handle_signal)
    uvicorn.run(webhook_app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
