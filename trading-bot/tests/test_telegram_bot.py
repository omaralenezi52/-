"""اختبار بوت تليجرام التفاعلي (منطق نقي، بلا شبكة)."""
from decimal import Decimal

from tradingbot.adapters.paper import PaperBroker
from tradingbot.agent.analyst import MarketView
from tradingbot.app import TradingApp
from tradingbot.config import Settings
from tradingbot.domain.models import Side, Signal, TradeMode
from tradingbot.notify.telegram_bot import TelegramBot


class ConfirmAnalyst:
    def analyze(self, symbol, features, evidences, regime):
        return MarketView(bias="BUY", confidence_adjustment=0.05, rationale="ok")


def strong_features():
    return {"close": 100.0, "ema_fast": 105.0, "ema_slow": 100.0, "ema_trend": 95.0,
            "rsi": 60.0, "atr": 2.0, "volume": 6000.0, "volume_sma": 4000.0}


def make_app(mode=TradeMode.SEMI_AUTO):
    settings = Settings(webhook_secret="x" * 12, mode=mode, telegram_chat_id="99")
    app = TradingApp(settings, broker=PaperBroker(starting_equity=Decimal("100000")))
    app.analyst = ConfirmAnalyst()
    app.journal = None   # عزل: بلا جورنال دائم في الاختبار
    return app


def signal():
    return Signal(symbol="AAPL", side=Side.BUY, price=Decimal("100"),
                  indicators=strong_features())


def test_semi_auto_registers_pending_without_executing():
    app = make_app()
    app.handle_signal(signal())
    assert len(app._pending) == 1                       # معلّقة
    assert app.broker.get_account_state().open_positions == 0  # لم تُنفّذ بعد


def test_approve_button_executes():
    app = make_app()
    app.handle_signal(signal())
    approval_id = next(iter(app._pending))
    bot = TelegramBot(app, chat_id="99")
    reply = bot.handle_update({"callback_query": {"data": f"exec:{approval_id}"}})
    assert "نُفّذت" in reply
    assert app.broker.get_account_state().open_positions == 1
    assert len(app._pending) == 0


def test_reject_button_discards():
    app = make_app()
    app.handle_signal(signal())
    approval_id = next(iter(app._pending))
    bot = TelegramBot(app, chat_id="99")
    reply = bot.handle_update({"callback_query": {"data": f"skip:{approval_id}"}})
    assert "التجاهل" in reply
    assert app.broker.get_account_state().open_positions == 0
    assert len(app._pending) == 0


def test_status_command():
    app = make_app()
    bot = TelegramBot(app, chat_id="99")
    reply = bot.handle_update({"message": {"text": "/status", "chat": {"id": 99}}})
    assert "حالة البوت" in reply and "SEMI_AUTO" in reply


def test_pause_and_resume():
    app = make_app()
    bot = TelegramBot(app, chat_id="99")
    bot.handle_update({"message": {"text": "/pause", "chat": {"id": 99}}})
    assert app.paused is True
    # موقوف ⇒ لا يعالج إشارة
    app.handle_signal(signal())
    assert len(app._pending) == 0
    bot.handle_update({"message": {"text": "/resume", "chat": {"id": 99}}})
    assert app.paused is False


def test_unauthorized_chat_ignored():
    app = make_app()
    bot = TelegramBot(app, chat_id="99")
    # محادثة مختلفة ⇒ تُتجاهل
    reply = bot.handle_update({"message": {"text": "/pause", "chat": {"id": 12345}}})
    assert reply is None
    assert app.paused is False
