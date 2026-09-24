"""
محرك الاختبار التاريخي (Backtesting Engine).

مبدأ الدقة الأهم: **لا Look-ahead**. عند كل شمعة i، القرار يُبنى على
الشموع المغلقة حتى i فقط، والتنفيذ يكون عند *فتح* الشمعة i+1 (لا يمكن
التداول على معلومة لم تكن متاحة وقتها). ونستخدم نفس compute_features
و DecisionEngine و RiskEngine المستخدمة في التداول الحي → تطابق مضمون.

يُختبر المنطق الحتمي (بدون LLM)؛ طبقة الذكاء غير حتمية ولا تُختبر تاريخياً.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from ..domain.decision import DecisionEngine
from ..domain.features import compute_features, features_to_evidence
from ..domain.models import AccountState, Decision, Side, Signal
from ..domain.risk import RiskEngine, RiskLimits
from ..pipeline import derive_levels, run_pipeline
from .metrics import PerformanceReport, build_report


@dataclass
class Trade:
    entry_index: int
    side: Side
    entry_price: float
    stop_loss: float
    take_profit: float
    quantity: float
    exit_index: int | None = None
    exit_price: float | None = None
    pnl: float = 0.0
    return_pct: float = 0.0

    @property
    def is_closed(self) -> bool:
        return self.exit_index is not None


@dataclass
class BacktestResult:
    report: PerformanceReport
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    def summary(self) -> str:
        r = self.report.as_dict()
        return (
            f"📊 نتائج الاختبار التاريخي\n"
            f"──────────────────────\n"
            f"إجمالي العائد:   {r['total_return_pct']}%\n"
            f"عدد الصفقات:     {r['num_trades']}\n"
            f"نسبة النجاح:     {r['win_rate']*100:.1f}%\n"
            f"عامل الربح:      {r['profit_factor']}\n"
            f"أقصى تراجع:      {r['max_drawdown_pct']}%\n"
            f"شارب / سورتينو:  {r['sharpe']} / {r['sortino']}\n"
            f"متوسط ربح/خسارة: {r['avg_win']} / {r['avg_loss']}\n"
            f"التوقّع للصفقة:  {r['expectancy']}"
        )


class Backtester:
    """
    يشغّل الاستراتيجية على بيانات تاريخية شمعة بشمعة.
    صفقة واحدة مفتوحة في الوقت الواحد (تبسيط آمن وواقعي للبداية).
    """

    def __init__(
        self,
        decision_engine: DecisionEngine | None = None,
        risk_limits: RiskLimits | None = None,
        initial_equity: float = 100_000.0,
        warmup: int = 200,           # شموع لتسخين المؤشرات (EMA200)
        fee_pct: float = 0.0005,     # عمولة/انزلاق تقديري لكل جهة (0.05%)
    ) -> None:
        self.decision_engine = decision_engine or DecisionEngine(min_agreeing=3)
        self.risk_limits = risk_limits or RiskLimits()
        self.initial_equity = initial_equity
        self.warmup = warmup
        self.fee_pct = fee_pct

    def run(self, df: pd.DataFrame) -> BacktestResult:
        equity = self.initial_equity
        trades: list[Trade] = []
        equity_curve: list[float] = [equity]
        open_trade: Trade | None = None

        n = len(df)
        for i in range(self.warmup, n - 1):
            # --- إدارة صفقة مفتوحة: هل ضُرب الوقف أو الهدف في شمعة i؟ ---
            if open_trade is not None:
                bar = df.iloc[i]
                exit_price = self._check_exit(open_trade, bar)
                if exit_price is not None:
                    equity += self._close_trade(open_trade, i, exit_price)
                    trades.append(open_trade)
                    equity_curve.append(equity)
                    open_trade = None
                continue  # لا ندخل صفقة جديدة والقديمة مفتوحة

            # --- بحث عن دخول جديد (قرار على الشموع المغلقة حتى i) ---
            window = df.iloc[: i + 1]
            try:
                features = compute_features(window)
            except ValueError:
                continue

            evidences = features_to_evidence(features)
            # نحدد الاتجاه المرشّح من غلبة الأدلة، ونبني إشارة موافقة
            buy_w = sum(e.weight for e in evidences if e.side == Side.BUY)
            sell_w = sum(e.weight for e in evidences if e.side == Side.SELL)
            side = Side.BUY if buy_w >= sell_w else Side.SELL

            # التنفيذ عند فتح الشمعة التالية (منع Look-ahead)
            entry_price = float(df.iloc[i + 1]["open"])
            signal = Signal(
                symbol="BT", side=side, price=Decimal(str(entry_price)),
                indicators=features,
            )
            account = AccountState(
                equity=Decimal(str(equity)), cash_available=Decimal(str(equity)),
            )
            risk_engine = RiskEngine(self.risk_limits)
            rec = run_pipeline(signal, evidences, account,
                               self.decision_engine, risk_engine)

            if rec.decision in (Decision.BUY, Decision.SELL) and rec.plan:
                open_trade = Trade(
                    entry_index=i + 1,
                    side=rec.plan.side,
                    entry_price=float(rec.plan.entry),
                    stop_loss=float(rec.plan.stop_loss),
                    take_profit=float(rec.plan.take_profit),
                    quantity=float(rec.plan.quantity),
                )

        # إغلاق أي صفقة متبقية بسعر آخر إغلاق
        if open_trade is not None:
            last_close = float(df.iloc[-1]["close"])
            equity += self._close_trade(open_trade, n - 1, last_close)
            trades.append(open_trade)
            equity_curve.append(equity)

        pnls = [t.pnl for t in trades]
        returns = [t.return_pct for t in trades]
        report = build_report(pnls, returns, equity_curve, self.initial_equity)
        return BacktestResult(report=report, trades=trades, equity_curve=equity_curve)

    def _check_exit(self, trade: Trade, bar: pd.Series) -> float | None:
        """
        هل ضُربت مستويات الخروج في هذه الشمعة؟
        محافظ: نفترض ضرب الوقف قبل الهدف عند غموض الترتيب داخل الشمعة.
        """
        high, low = float(bar["high"]), float(bar["low"])
        if trade.side == Side.BUY:
            if low <= trade.stop_loss:
                return trade.stop_loss
            if high >= trade.take_profit:
                return trade.take_profit
        else:  # SELL
            if high >= trade.stop_loss:
                return trade.stop_loss
            if low <= trade.take_profit:
                return trade.take_profit
        return None

    def _close_trade(self, trade: Trade, exit_index: int, exit_price: float) -> float:
        """يغلق الصفقة ويُرجع صافي الربح/الخسارة (مع العمولة)."""
        direction = 1 if trade.side == Side.BUY else -1
        gross = (exit_price - trade.entry_price) * direction * trade.quantity
        fees = (trade.entry_price + exit_price) * trade.quantity * self.fee_pct
        pnl = gross - fees
        cost_basis = trade.entry_price * trade.quantity

        trade.exit_index = exit_index
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.return_pct = (pnl / cost_basis) if cost_basis > 0 else 0.0
        return pnl
