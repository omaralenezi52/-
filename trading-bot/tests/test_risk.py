"""اختبارات حاكم المخاطر — أخطر جزء، لذا الأكثر تغطية."""
from decimal import Decimal

import pytest

from tradingbot.domain.models import AccountState, Side, Signal
from tradingbot.domain.risk import RiskEngine, RiskLimits


def make_signal(side=Side.BUY, price="100"):
    return Signal(symbol="AAPL", side=side, price=Decimal(price))


def make_account(equity="100000", cash="100000", positions=0, pnl="0"):
    return AccountState(
        equity=Decimal(equity),
        cash_available=Decimal(cash),
        open_positions=positions,
        realized_pnl_today=Decimal(pnl),
    )


def test_approves_valid_buy_and_sizes_from_stop():
    eng = RiskEngine(RiskLimits())
    d = eng.evaluate(
        make_signal(), Decimal("98"), Decimal("106"),
        make_account(), confidence=0.8,
    )
    assert d.approved
    # مخاطرة 1% من 100k = 1000$، مسافة الوقف 2$ ⇒ 500 عقد (قبل حد الانكشاف)
    # حد الانكشاف 25% من 100k = 25000$ / 100 = 250 عقد ⇒ يُقلَّص إلى 250
    assert d.plan.quantity == Decimal("250")
    # مسافة الوقف 2$، مسافة الهدف 6$ ⇒ نسبة 3.00
    assert d.plan.risk_reward_ratio == Decimal("3.00")


def test_rejects_low_confidence():
    eng = RiskEngine(RiskLimits(min_confidence=0.7))
    d = eng.evaluate(make_signal(), Decimal("98"), Decimal("106"),
                     make_account(), confidence=0.5)
    assert not d.approved and "الثقة" in d.reason


def test_daily_loss_circuit_breaker():
    eng = RiskEngine(RiskLimits(max_daily_loss_pct=Decimal("0.03")))
    # خسر 3% من 100k = 3000$ ⇒ يجب أن يتوقف
    d = eng.evaluate(make_signal(), Decimal("98"), Decimal("106"),
                     make_account(pnl="-3000"), confidence=0.9)
    assert not d.approved and "الخسارة اليومي" in d.reason


def test_rejects_bad_risk_reward():
    eng = RiskEngine(RiskLimits(min_risk_reward=Decimal("2")))
    # مخاطرة 2 مقابل عائد 1 ⇒ RR=0.5 مرفوض
    d = eng.evaluate(make_signal(), Decimal("98"), Decimal("101"),
                     make_account(), confidence=0.9)
    assert not d.approved and "العائد/المخاطرة" in d.reason


def test_rejects_max_open_positions():
    eng = RiskEngine(RiskLimits(max_open_positions=3))
    d = eng.evaluate(make_signal(), Decimal("98"), Decimal("106"),
                     make_account(positions=3), confidence=0.9)
    assert not d.approved and "المفتوحة" in d.reason


def test_rejects_illogical_levels_for_buy():
    eng = RiskEngine()
    # في الشراء، الوقف أعلى من الدخول = غير منطقي
    d = eng.evaluate(make_signal(), Decimal("102"), Decimal("106"),
                     make_account(), confidence=0.9)
    assert not d.approved


def test_sell_side_levels_valid():
    eng = RiskEngine()
    d = eng.evaluate(
        make_signal(side=Side.SELL, price="100"),
        Decimal("102"), Decimal("94"),   # وقف أعلى، هدف أقل = صحيح للبيع
        make_account(), confidence=0.9,
    )
    assert d.approved and d.plan.side == Side.SELL


def test_insufficient_cash_rejected():
    eng = RiskEngine(RiskLimits(max_position_pct=Decimal("1")))
    # نقد قليل جداً لا يكفي لأي عقد بالحجم المحسوب
    d = eng.evaluate(make_signal(), Decimal("99.9"), Decimal("100.3"),
                     make_account(equity="100000", cash="10"), confidence=0.9)
    assert not d.approved


def test_zero_stop_distance_rejected():
    eng = RiskEngine()
    d = eng.evaluate(make_signal(price="100"), Decimal("100"), Decimal("110"),
                     make_account(), confidence=0.9)
    assert not d.approved
