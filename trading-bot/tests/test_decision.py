"""اختبارات محرك القرار وتوافق الأدلة (Confluence)."""
from decimal import Decimal

from tradingbot.domain.decision import DecisionEngine, Evidence
from tradingbot.domain.models import Decision, MarketRegime, Side, Signal


def sig(side=Side.BUY, indicators=None):
    return Signal(symbol="AAPL", side=side, price=Decimal("100"),
                  indicators=indicators or {})


def test_confluence_requires_min_agreement():
    eng = DecisionEngine(min_agreeing=3)
    # دليلان فقط يؤيدان الشراء ⇒ لا يكفي ⇒ WAIT
    evs = [
        Evidence("trend", Side.BUY, 0.8),
        Evidence("momentum", Side.BUY, 0.7),
    ]
    r = eng.evaluate(sig(), evs)
    assert r.decision == Decision.WAIT


def test_confluence_buy_with_enough_agreement():
    eng = DecisionEngine(min_agreeing=3)
    evs = [
        Evidence("trend", Side.BUY, 0.9, "EMA20>EMA50"),
        Evidence("momentum", Side.BUY, 0.8, "RSI صحي"),
        Evidence("volume", Side.BUY, 0.7, "حجم مرتفع"),
    ]
    r = eng.evaluate(sig(), evs)
    assert r.decision == Decision.BUY
    assert r.confidence > 0.9
    assert len(r.reasons) == 3


def test_conflicting_signal_direction_waits():
    eng = DecisionEngine(min_agreeing=2)
    # الأدلة تؤيد البيع لكن الإشارة شراء ⇒ عدم توافق ⇒ WAIT
    evs = [
        Evidence("trend", Side.SELL, 0.9),
        Evidence("momentum", Side.SELL, 0.8),
    ]
    r = eng.evaluate(sig(side=Side.BUY), evs)
    assert r.decision == Decision.WAIT


def test_regime_ranging_from_low_adx():
    eng = DecisionEngine()
    r = eng.detect_regime({"adx": 15})
    assert r == MarketRegime.RANGING


def test_regime_trending_up():
    eng = DecisionEngine()
    r = eng.detect_regime({"ema_fast": 105, "ema_slow": 100})
    assert r == MarketRegime.TRENDING_UP


def test_no_evidence_waits():
    eng = DecisionEngine()
    assert eng.evaluate(sig(), []).decision == Decision.WAIT
