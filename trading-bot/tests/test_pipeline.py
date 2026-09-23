"""اختبار الترابط الكامل من الإشارة إلى التوصية."""
from decimal import Decimal

from tradingbot.domain.decision import DecisionEngine, Evidence
from tradingbot.domain.models import AccountState, Decision, Side, Signal
from tradingbot.domain.risk import RiskEngine, RiskLimits
from tradingbot.pipeline import run_pipeline


def build():
    return (
        DecisionEngine(min_agreeing=3),
        RiskEngine(RiskLimits(min_confidence=0.6)),
        AccountState(equity=Decimal("100000"), cash_available=Decimal("100000")),
    )


def buy_signal():
    return Signal(symbol="AAPL", side=Side.BUY, price=Decimal("100"),
                  indicators={"atr": 2, "ema_fast": 105, "ema_slow": 100})


def strong_evidence():
    return [
        Evidence("trend", Side.BUY, 0.9, "اتجاه صاعد"),
        Evidence("momentum", Side.BUY, 0.8, "زخم قوي"),
        Evidence("volume", Side.BUY, 0.7, "حجم داعم"),
    ]


def test_full_pipeline_produces_actionable_recommendation():
    de, re, acc = build()
    rec = run_pipeline(buy_signal(), strong_evidence(), acc, de, re,
                       rationale="توافق قوي")
    assert rec.decision == Decision.BUY
    assert rec.is_actionable
    assert rec.plan.stop_loss < rec.plan.entry < rec.plan.take_profit
    assert rec.plan.risk_reward_ratio >= Decimal("1.5")


def test_pipeline_waits_on_weak_evidence():
    de, re, acc = build()
    weak = [Evidence("trend", Side.BUY, 0.5)]
    rec = run_pipeline(buy_signal(), weak, acc, de, re)
    assert rec.decision == Decision.WAIT
    assert rec.plan is None


def test_pipeline_rejects_when_risk_blocks():
    de = DecisionEngine(min_agreeing=3)
    re = RiskEngine(RiskLimits(min_confidence=0.6, max_open_positions=1))
    acc = AccountState(equity=Decimal("100000"),
                       cash_available=Decimal("100000"), open_positions=1)
    rec = run_pipeline(buy_signal(), strong_evidence(), acc, de, re)
    assert rec.decision == Decision.REJECT
    assert rec.rejection_reason
