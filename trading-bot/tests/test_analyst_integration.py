"""اختبارات تكامل طبقة الذكاء مع الـ Pipeline (بمحلل وهمي، بدون شبكة)."""
from decimal import Decimal

from tradingbot.agent.analyst import MarketView, NeutralAnalyst
from tradingbot.domain.decision import DecisionEngine, Evidence
from tradingbot.domain.models import AccountState, Decision, Side, Signal
from tradingbot.domain.risk import RiskEngine, RiskLimits
from tradingbot.pipeline import run_pipeline_with_analyst


class FakeAnalyst:
    """محلل وهمي يُرجع رأياً محدداً مسبقاً لاختبار سلوك الـ Pipeline."""
    def __init__(self, view: MarketView):
        self.view = view
        self.called = False

    def analyze(self, symbol, features, evidences, regime):
        self.called = True
        return self.view


def setup():
    return (
        DecisionEngine(min_agreeing=3),
        RiskEngine(RiskLimits(min_confidence=0.6)),
        AccountState(equity=Decimal("100000"), cash_available=Decimal("100000")),
    )


def buy_signal():
    return Signal(symbol="AAPL", side=Side.BUY, price=Decimal("100"),
                  indicators={"atr": 2, "ema_fast": 105, "ema_slow": 100,
                              "close": 100, "rsi": 60, "volume": 5000})


def strong_evidence():
    return [
        Evidence("trend", Side.BUY, 0.9, "صاعد"),
        Evidence("momentum", Side.BUY, 0.8, "زخم"),
        Evidence("volume", Side.BUY, 0.7, "حجم"),
    ]


def test_analyst_veto_forces_wait():
    de, re, acc = setup()
    analyst = FakeAnalyst(MarketView(bias="BUY", veto=True, rationale="مصيدة ثيران"))
    rec = run_pipeline_with_analyst(buy_signal(), strong_evidence(), acc, de, re, analyst)
    assert analyst.called
    assert rec.decision == Decision.WAIT
    assert rec.rejection_reason == "فيتو المحلل"


def test_analyst_neutral_forces_wait():
    de, re, acc = setup()
    analyst = FakeAnalyst(MarketView(bias="NEUTRAL", rationale="غير واضح"))
    rec = run_pipeline_with_analyst(buy_signal(), strong_evidence(), acc, de, re, analyst)
    assert rec.decision == Decision.WAIT


def test_analyst_confirm_allows_actionable():
    de, re, acc = setup()
    analyst = FakeAnalyst(MarketView(bias="BUY", confidence_adjustment=0.1,
                                     rationale="توافق ممتاز"))
    rec = run_pipeline_with_analyst(buy_signal(), strong_evidence(), acc, de, re, analyst)
    assert rec.decision == Decision.BUY
    assert rec.is_actionable
    assert rec.rationale == "توافق ممتاز"


def test_analyst_negative_adjustment_can_trigger_risk_reject():
    de = DecisionEngine(min_agreeing=3)
    re = RiskEngine(RiskLimits(min_confidence=0.95))  # حد ثقة عالٍ
    acc = AccountState(equity=Decimal("100000"), cash_available=Decimal("100000"))
    # المحلل يخفض الثقة ⇒ تحت الحد ⇒ حاكم المخاطر يرفض
    analyst = FakeAnalyst(MarketView(bias="BUY", confidence_adjustment=-0.3))
    rec = run_pipeline_with_analyst(buy_signal(), strong_evidence(), acc, de, re, analyst)
    assert rec.decision == Decision.REJECT


def test_neutral_analyst_is_safe_default():
    de, re, acc = setup()
    rec = run_pipeline_with_analyst(buy_signal(), strong_evidence(), acc, de, re,
                                    NeutralAnalyst())
    # المحلل المحايد يرجّع NEUTRAL ⇒ انتظار آمن (لا يخترع صفقات)
    assert rec.decision == Decision.WAIT
