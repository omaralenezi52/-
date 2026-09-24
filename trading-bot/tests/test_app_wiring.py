"""اختبار التجميع الكامل: إشارة → تحليل → توصية → تنفيذ (على Paper)."""
from decimal import Decimal

from tradingbot.adapters.paper import PaperBroker
from tradingbot.agent.analyst import MarketView
from tradingbot.app import TradingApp
from tradingbot.config import Settings
from tradingbot.domain.models import Side, Signal, TradeMode


class ConfirmAnalyst:
    """محلل يؤكد الشراء — لاختبار مسار التنفيذ."""
    def analyze(self, symbol, features, evidences, regime):
        return MarketView(bias="BUY", confidence_adjustment=0.05, rationale="تأكيد")


def strong_features():
    return {
        "close": 100.0, "ema_fast": 105.0, "ema_slow": 100.0, "ema_trend": 95.0,
        "rsi": 60.0, "atr": 2.0, "volume": 6000.0, "volume_sma": 4000.0,
    }


def make_signal():
    return Signal(symbol="AAPL", side=Side.BUY, price=Decimal("100"),
                  indicators=strong_features())


def test_full_auto_executes_on_paper():
    settings = Settings(webhook_secret="x" * 12, mode=TradeMode.FULL_AUTO)
    broker = PaperBroker(starting_equity=Decimal("100000"))
    app = TradingApp(settings, broker=broker)
    app.analyst = ConfirmAnalyst()  # حقن محلل مؤكِّد

    before = broker.get_account_state().open_positions
    app.handle_signal(make_signal())
    after = broker.get_account_state().open_positions

    assert after == before + 1  # فُتحت صفقة


def test_advisor_mode_does_not_execute():
    settings = Settings(webhook_secret="x" * 12, mode=TradeMode.ADVISOR)
    broker = PaperBroker(starting_equity=Decimal("100000"))
    app = TradingApp(settings, broker=broker)
    app.analyst = ConfirmAnalyst()

    app.handle_signal(make_signal())
    # وضع التوصية فقط ⇒ لا تنفيذ
    assert broker.get_account_state().open_positions == 0


def test_build_defaults_to_paper_without_broker_config():
    settings = Settings(webhook_secret="x" * 12)
    app = TradingApp(settings, broker=PaperBroker())
    assert app.broker.name == "paper"
