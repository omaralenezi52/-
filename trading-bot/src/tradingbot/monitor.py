"""
المراقبة والنبض (Monitoring & Dead-man switch) — طبقة احترافية.

المبدأ المؤسسي: نظام يدير مالاً يجب أن يراقب نفسه. لو توقّف عن قراءة
السوق (تعطّل مزوّد، انقطاع شبكة) دون أن يصرخ، فهو أخطر من نظام يتوقف
بوضوح. هذه الطبقة ترصد آخر دورة ناجحة وتنبّه إذا تجمّد.

- heartbeat: يُحدّث عند كل دورة ناجحة.
- dead-man: لو مرّ وقت أطول من العتبة بلا دورة ناجحة → تنبيه تليجرام.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("tradingbot.monitor")


class HealthMonitor:
    def __init__(self, notifier=None, stale_after_seconds: int = 5400) -> None:
        # 5400s = 90 دقيقة: دورة الساعة + هامش قبل اعتبار البوت متجمّداً
        self.notifier = notifier
        self.stale_after = stale_after_seconds
        self.last_success: datetime | None = None
        self.last_error: str | None = None
        self._alerted_stale = False

    def record_success(self) -> None:
        """يُستدعى عند دورة قراءة ناجحة."""
        self.last_success = datetime.now(timezone.utc)
        self.last_error = None
        self._alerted_stale = False

    def record_error(self, error: str) -> None:
        self.last_error = error[:120]

    def seconds_since_success(self) -> float | None:
        if self.last_success is None:
            return None
        return (datetime.now(timezone.utc) - self.last_success).total_seconds()

    def check(self) -> bool:
        """
        يفحص الصحة. يُرجع True إذا سليم، False إذا متجمّد.
        ينبّه مرة واحدة عند أول تجمّد (لا يكرّر الإزعاج).
        """
        elapsed = self.seconds_since_success()
        if elapsed is None:
            return True  # لم تبدأ بعد — ليس تجمّداً
        if elapsed > self.stale_after:
            if not self._alerted_stale:
                self._alerted_stale = True
                msg = (f"🔴 تنبيه: البوت لم يقرأ السوق منذ "
                       f"{int(elapsed/60)} دقيقة. تحقّق من المزوّد/الشبكة.")
                logger.error(msg)
                if self.notifier is not None:
                    self.notifier.send_text(msg)
            return False
        return True

    def health_text(self) -> str:
        """ملخص الصحة لأمر /health في تليجرام."""
        elapsed = self.seconds_since_success()
        if elapsed is None:
            status = "لم تبدأ الدورات بعد"
        elif elapsed > self.stale_after:
            status = f"🔴 متجمّد ({int(elapsed/60)} دقيقة)"
        else:
            status = f"🟢 سليم (آخر قراءة قبل {int(elapsed)} ثانية)"
        err = f"\nآخر خطأ: {self.last_error}" if self.last_error else ""
        return f"❤️ صحة النظام: {status}{err}"
