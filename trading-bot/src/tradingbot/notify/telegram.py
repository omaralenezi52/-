"""
تنسيق وإرسال التوصيات عبر تليجرام.

الإرسال الفعلي معزول خلف واجهة بسيطة ليبقى المنطق قابلاً للاختبار
دون شبكة. صياغة الرسالة (format_recommendation) نقية وقابلة للاختبار.
"""
from __future__ import annotations

import logging

from ..domain.models import Decision, Recommendation

logger = logging.getLogger("tradingbot.telegram")


def format_recommendation(rec: Recommendation) -> str:
    """يبني نص التوصية بالأرقام (نقي، بلا آثار جانبية)."""
    if rec.decision == Decision.REJECT:
        return (
            f"⛔ رُفضت فرصة {rec.symbol}\n"
            f"السبب: {rec.rejection_reason or 'غير محدد'}"
        )
    if not rec.is_actionable or rec.plan is None:
        return (
            f"⏳ انتظار — {rec.symbol}\n"
            f"الثقة {rec.confidence:.0%} | النظام: {rec.regime.value}\n"
            f"لا يوجد توافق كافٍ للدخول الآن."
        )

    p = rec.plan
    emoji = "🟢" if rec.decision == Decision.BUY else "🔴"
    reasons = "\n".join(f"  • {r}" for r in rec.reasons) or "  • —"
    return (
        f"{emoji} توصية {rec.decision.value} — {rec.symbol}\n"
        f"──────────────────────\n"
        f"🎯 الثقة: {rec.confidence:.0%} | النظام: {rec.regime.value}\n"
        f"💰 الدخول:      {p.entry}\n"
        f"🛑 وقف الخسارة: {p.stop_loss}\n"
        f"🎯 الهدف:       {p.take_profit}\n"
        f"⚖️ العائد/المخاطرة: 1 : {p.risk_reward_ratio}\n"
        f"📈 الكمية: {p.quantity} | المخاطرة: {p.risk_amount}\n"
        f"──────────────────────\n"
        f"🧠 التحليل:\n{rec.rationale or '—'}\n"
        f"📊 أدلة التوافق:\n{reasons}"
    )


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    def send(self, rec: Recommendation, approval_id: str | None = None) -> bool:
        """
        يرسل التوصية. لو مُرِّر approval_id، يضيف أزرار ✅/❌ (وضع SEMI_AUTO).
        """
        text = format_recommendation(rec)
        reply_markup = None
        if approval_id:
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "✅ تنفيذ", "callback_data": f"exec:{approval_id}"},
                    {"text": "❌ تجاهل", "callback_data": f"skip:{approval_id}"},
                ]]
            }
        return self.send_text(text, reply_markup)

    def send_text(self, text: str, reply_markup: dict | None = None) -> bool:
        """يرسل نصاً عاماً (للتنبيهات وردود الأوامر)."""
        if not self.token or not self.chat_id:
            logger.info("تليجرام غير مُهيّأ — الرسالة:\n%s", text)
            return False
        try:
            import httpx  # استيراد كسول

            payload = {"chat_id": self.chat_id, "text": text}
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            resp = httpx.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("فشل إرسال رسالة تليجرام")
            return False
