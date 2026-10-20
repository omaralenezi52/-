"""
التحقق المتدرّج الأمامي (Walk-Forward Validation) — المعيار الاحترافي.

المشكلة في الـ Backtest العادي: قد يكون النظام "حفظ" الماضي (Overfitting)،
فيبدو ممتازاً تاريخياً ويفشل مستقبلاً. الحل المؤسسي: نقسّم البيانات إلى
نوافذ متتالية، ونختبر كل نافذة على بيانات *لم تُستخدم* قبلها — محاكاة
للأداء الحقيقي عبر الزمن.

يُرجع أداء كل نافذة + المتوسط، فنرى هل النظام ثابت أم يعتمد على فترة واحدة.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .engine import Backtester


@dataclass
class WindowResult:
    window: int
    bars: int
    total_return_pct: float
    win_rate: float
    num_trades: int
    max_drawdown_pct: float


@dataclass
class WalkForwardReport:
    windows: list[WindowResult]

    @property
    def avg_return(self) -> float:
        return _mean([w.total_return_pct for w in self.windows])

    @property
    def avg_win_rate(self) -> float:
        return _mean([w.win_rate for w in self.windows])

    @property
    def consistency(self) -> float:
        """نسبة النوافذ الرابحة — مقياس الثبات (0..1). عالٍ = غير محفوظ."""
        if not self.windows:
            return 0.0
        profitable = sum(1 for w in self.windows if w.total_return_pct > 0)
        return profitable / len(self.windows)

    def summary(self) -> str:
        lines = ["🔬 التحقق المتدرّج الأمامي (Walk-Forward)"]
        for w in self.windows:
            lines.append(
                f"نافذة {w.window}: عائد {w.total_return_pct:.1f}% | "
                f"نجاح {w.win_rate*100:.0f}% | صفقات {w.num_trades} | "
                f"تراجع {w.max_drawdown_pct:.1f}%"
            )
        lines.append(
            f"── المتوسط: عائد {self.avg_return:.1f}% | "
            f"نجاح {self.avg_win_rate*100:.0f}% | "
            f"ثبات {self.consistency*100:.0f}% من النوافذ رابحة"
        )
        return "\n".join(lines)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def walk_forward(
    df: pd.DataFrame,
    n_windows: int = 4,
    warmup: int = 200,
    backtester: Backtester | None = None,
) -> WalkForwardReport:
    """
    يقسّم البيانات إلى n_windows نافذة متتالية، ويختبر كل واحدة مستقلة.
    كل نافذة تحمل فترة تسخين خاصة بها (warmup) لحساب المؤشرات.
    """
    bt = backtester or Backtester(warmup=warmup)
    n = len(df)
    if n < (warmup + 50) * 1:
        raise ValueError("بيانات غير كافية للتحقق المتدرّج")

    # حجم كل نافذة (بعد التسخين) — نافذة تحتوي warmup + فترة اختبار
    test_size = (n - warmup) // n_windows
    if test_size < 50:
        raise ValueError("النوافذ صغيرة جداً — قلّل عددها أو زد البيانات")

    results: list[WindowResult] = []
    for i in range(n_windows):
        start = i * test_size
        end = warmup + (i + 1) * test_size
        window_df = df.iloc[start:end].reset_index(drop=True)
        if len(window_df) < warmup + 20:
            continue
        res = bt.run(window_df)
        r = res.report
        results.append(WindowResult(
            window=i + 1,
            bars=len(window_df),
            total_return_pct=r.total_return_pct,
            win_rate=r.win_rate,
            num_trades=r.num_trades,
            max_drawdown_pct=r.max_drawdown_pct,
        ))

    return WalkForwardReport(windows=results)
