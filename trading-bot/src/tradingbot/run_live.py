"""
تشغيل الحلقة الحية على جدول (عند إغلاق الشموع).

    python -m tradingbot.run_live AAPL MSFT NVDA

يقرأ الإعدادات من .env. لا يستخدم while-sleep عشوائياً — يشتغل عند
إغلاق الشمعة (بعد دقيقة من رأس الساعة افتراضياً). يسجّل الأخطاء ويكمل.
"""
from __future__ import annotations

import logging
import sys
import threading
import time

import schedule

from .app import TradingApp
from .config import Settings
from .data.alpaca_feed import AlpacaDataFeed
from .live_loop import LiveLoop
from .notify.telegram_bot import TelegramBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tradingbot.run_live")


def main() -> None:
    symbols = sys.argv[1:] or ["AAPL"]
    settings = Settings.from_env()
    app = TradingApp(settings)
    feed = AlpacaDataFeed(settings.alpaca_api_key, settings.alpaca_secret_key)
    loop = LiveLoop(app, feed, symbols, timeframe="1h")

    logger.info("بدء الحلقة الحية | الرموز=%s | الوضع=%s", symbols, settings.mode.value)

    # بوت تليجرام التفاعلي في خيط منفصل (أزرار الموافقة + الأوامر)
    if settings.telegram_token and settings.telegram_chat_id:
        bot = TelegramBot(app, settings.telegram_token, settings.telegram_chat_id)
        threading.Thread(target=bot.run, daemon=True).start()
        logger.info("بوت تليجرام التفاعلي يعمل")

    # يشتغل بعد دقيقة من رأس كل ساعة (الشمعة أُغلقت وثُبّتت)
    schedule.every().hour.at(":01").do(loop.run_cycle)
    loop.run_cycle()  # دورة فورية عند الإقلاع

    while True:
        schedule.run_pending()
        time.sleep(5)


if __name__ == "__main__":
    main()
