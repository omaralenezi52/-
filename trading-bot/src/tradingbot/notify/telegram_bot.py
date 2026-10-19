"""
بوت تليجرام التفاعلي — يستقبل ضغطات الأزرار والأوامر ويتحكّم في البوت.

التصميم: منطق معالجة التحديث (handle_update) *نقي وقابل للاختبار* بلا شبكة،
وحلقة الاستطلاع (poll) منفصلة. يربط المستخدم بالتطبيق:
- زر ✅/❌ → تنفيذ/تجاهل توصية معلّقة (SEMI_AUTO).
- /status → ملخص حالة البوت.
- /pause و /resume → إيقاف/استئناف التداول.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger("tradingbot.telegram_bot")


class TelegramBot:
    def __init__(self, app, token: str = "", chat_id: str = "") -> None:
        self.app = app                      # TradingApp
        self.token = token
        self.chat_id = str(chat_id)
        self._offset = 0                    # آخر update_id مُعالَج

    def handle_update(self, update: dict) -> str | None:
        """
        يعالج تحديثاً واحداً ويُرجع نص الرد (أو None).
        نقي: لا شبكة — يُختبر بسهولة.
        """
        # ضغطة زر (callback)
        callback = update.get("callback_query")
        if callback:
            data = callback.get("data", "")
            if data.startswith("exec:"):
                return self.app.approve(data.split(":", 1)[1])
            if data.startswith("skip:"):
                return self.app.reject(data.split(":", 1)[1])
            return None

        # رسالة نصّية (أمر)
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()

        # تقييد الوصول: فقط المحادثة المصرّح لها (أمان)
        sender_chat = str((message.get("chat") or {}).get("id", ""))
        if self.chat_id and sender_chat and sender_chat != self.chat_id:
            logger.warning("رسالة من محادثة غير مصرّح لها: %s", sender_chat)
            return None

        if text in ("/start", "/help"):
            return ("🤖 أوامر البوت:\n"
                    "/status — حالة البوت والحساب\n"
                    "/diag — فحص السوق الآن (دليل القراءة)\n"
                    "/stats — أداء البوت من الذاكرة\n"
                    "/pause — إيقاف التداول مؤقتاً\n"
                    "/resume — استئناف التداول")
        if text == "/status":
            return self.app.status_text()
        if text == "/diag":
            return self.app.diagnose_text()
        if text == "/stats":
            return self.app.stats_text()
        if text == "/pause":
            self.app.paused = True
            return "⏸️ أُوقف التداول مؤقتاً. /resume للاستئناف."
        if text == "/resume":
            self.app.paused = False
            return "▶️ استُؤنف التداول."
        return None

    # ---------------- حلقة الاستطلاع (شبكة) ---------------- #
    def poll_once(self) -> None:  # pragma: no cover - يتطلب شبكة
        import httpx
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        resp = httpx.get(url, params={"offset": self._offset + 1, "timeout": 25},
                         timeout=30.0)
        for update in resp.json().get("result", []):
            self._offset = update["update_id"]
            try:
                reply = self.handle_update(update)
            except Exception:
                logger.exception("فشل معالجة تحديث تليجرام")
                reply = "⚠️ حدث خطأ أثناء تنفيذ الأمر — تحقّق من السجلّ."
            if reply:
                self.app.notifier.send_text(reply)

    def run(self) -> None:  # pragma: no cover - حلقة لا نهائية
        logger.info("بدء بوت تليجرام التفاعلي")
        while True:
            try:
                self.poll_once()
            except Exception:
                logger.exception("خطأ في استطلاع تليجرام — إعادة المحاولة")
                time.sleep(5)
