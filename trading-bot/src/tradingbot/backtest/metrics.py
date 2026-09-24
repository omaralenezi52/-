"""
مقاييس أداء الاستراتيجية — دوال نقية قابلة للاختبار بدقة.

كلها تعمل على قوائم أرقام بايثون بسيطة (لا اعتماد على حالة)، فتُختبر
بمدخلات معروفة ومخرجات متوقعة. هذه هي الأرقام التي تُعرض للعميل لإثبات
الأداء بموضوعية بدل الوعود.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceReport:
    total_return_pct: float
    num_trades: int
    win_rate: float          # 0..1
    profit_factor: float     # إجمالي الأرباح / إجمالي الخسائر
    avg_win: float
    avg_loss: float
    expectancy: float        # متوسط الربح المتوقع لكل صفقة
    max_drawdown_pct: float  # أقصى تراجع من القمة (قيمة موجبة)
    sharpe: float            # لكل صفقة (mean/std)
    sortian: float           # مثل Sharpe لكن بانحراف الخسائر فقط

    def as_dict(self) -> dict:
        return {
            "total_return_pct": round(self.total_return_pct, 2),
            "num_trades": self.num_trades,
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "expectancy": round(self.expectancy, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "sharpe": round(self.sharpe, 3),
            "sortino": round(self.sortian, 3),
        }


def max_drawdown(equity_curve: list[float]) -> float:
    """أقصى تراجع نسبي من قمة سابقة (قيمة موجبة %). فارغ ⇒ 0."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
    return max_dd * 100


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


# حد تسامح: انحراف أصغر منه يُعتبر صفراً (تجنّب ضجيج الفاصلة العائمة)
_EPS = 1e-12


def sharpe_ratio(returns: list[float]) -> float:
    """نسبة شارب لكل صفقة (متوسط العائد / تقلبه). صفر إذا لا تقلب."""
    sd = _std(returns)
    return _mean(returns) / sd if sd > _EPS else 0.0


def sortino_ratio(returns: list[float]) -> float:
    """مثل شارب لكن يعاقب تقلب الخسائر فقط (الأنسب للمخاطر)."""
    downside = [r for r in returns if r < 0]
    dd = _std(downside) if len(downside) >= 2 else 0.0
    return _mean(returns) / dd if dd > _EPS else 0.0


def build_report(
    trade_pnls: list[float],
    trade_returns: list[float],
    equity_curve: list[float],
    initial_equity: float,
) -> PerformanceReport:
    """يجمع كل المقاييس من نتائج الصفقات ومنحنى رأس المال."""
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    num = len(trade_pnls)
    win_rate = len(wins) / num if num else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )
    avg_win = _mean(wins)
    avg_loss = _mean(losses)
    expectancy = _mean(trade_pnls)

    final_equity = equity_curve[-1] if equity_curve else initial_equity
    total_return = ((final_equity - initial_equity) / initial_equity * 100
                    if initial_equity > 0 else 0.0)

    return PerformanceReport(
        total_return_pct=total_return,
        num_trades=num,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        expectancy=expectancy,
        max_drawdown_pct=max_drawdown(equity_curve),
        sharpe=sharpe_ratio(trade_returns),
        sortian=sortino_ratio(trade_returns),
    )
