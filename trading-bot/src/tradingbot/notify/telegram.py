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

    def send(self, rec: Recommendation) -> bool:
        text = format_recommendation(rec)
        if not self.token or not self.chat_id:
            logger.info("تليجرام غير مُهيّأ — الرسالة:\n%s", text)
            return False
        try:
            import httpx  # استيراد كسول

            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            resp = httpx.post(
                url,
                json={"chat_id": self.chat_id, "text": text},
                timeout=10.0,
            )
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("فشل إرسال رسالة تليجرام")
            return False
