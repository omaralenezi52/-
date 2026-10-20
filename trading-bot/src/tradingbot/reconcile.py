"""
المطابقة (Reconciliation) — طبقة موثوقية احترافية.

المبدأ المؤسسي: المنصة هي مصدر الحقيقة، لا ذاكرة البوت. بعد انقطاع أو
إعادة تشغيل، قد تختلف حالة البوت عن الواقع (صفقة أُغلقت، fill جزئي،
أمر لم يُنفّذ). هذه الطبقة تقارن وتبلّغ عن أي تضارب.

تُشغّل عند الإقلاع ودورياً. لا تتداول — ترصد وتبلّغ فقط (آمنة).
"""
from __future__ import annotations

import logging

logger = logging.getLogger("tradingbot.reconcile")


class Reconciler:
    def __init__(self, broker, journal=None, notifier=None) -> None:
        self.broker = broker
        self.journal = journal
        self.notifier = notifier

    def reconcile(self) -> dict:
        """
        يقارن صفقات المنصة الفعلية بسجلّ البوت ويُرجع تقريراً.
        يبلّغ تليجرام عند وجود تضارب.
        """
        report = {"broker_positions": 0, "journal_open": 0, "discrepancies": []}

        # 1) الحالة الفعلية من المنصة (مصدر الحقيقة)
        try:
            account = self.broker.get_account_state()
            report["broker_positions"] = account.open_positions
        except Exception as exc:
            logger.exception("تعذّر جلب حالة المنصة للمطابقة")
            report["discrepancies"].append(f"تعذّر الوصول للمنصة: {str(exc)[:80]}")
            self._notify(report)
            return report

        # 2) ما يظنه البوت (من الجورنال)
        if self.journal is not None:
            try:
                stats = self.journal.stats()
                report["journal_open"] = stats["open_trades"]
            except Exception:
                logger.exception("تعذّر قراءة الجورنال للمطابقة")

        # 3) كشف التضارب: عدد الصفقات في البوت ≠ المنصة
        if self.journal is not None:
            if report["journal_open"] != report["broker_positions"]:
                msg = (
                    f"تضارب: البوت يسجّل {report['journal_open']} صفقة مفتوحة، "
                    f"المنصة فيها {report['broker_positions']}"
                )
                report["discrepancies"].append(msg)
                logger.warning(msg)

        self._notify(report)
        return report

    def _notify(self, report: dict) -> None:
        if not report["discrepancies"]:
            logger.info("المطابقة: متطابق (المنصة=%s)", report["broker_positions"])
            return
        if self.notifier is not None:
            lines = "\n".join(f"• {d}" for d in report["discrepancies"])
            self.notifier.send_text(f"⚠️ تقرير المطابقة — تضارب:\n{lines}")
