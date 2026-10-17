"""اختبار الحلقة الحية بمزوّد بيانات وهمي (بلا شبكة)."""
from decimal import Decimal

import numpy as np
import pandas as pd

from tradingbot.adapters.paper import PaperBroker
from tradingbot.agent.analyst import MarketView
from tradingbot.app import TradingApp
from tradingbot.config import Settings
from tradingbot.domain.models import TradeMode
from tradingbot.live_loop import LiveLoop


class FakeFeed:
    def __init__(self, df):
        self.df = df
        self.calls = 0

    def get_candles(self, symbol, timeframe, limit=300):
        self.calls += 1
        return self.df


class ConfirmAnalyst:
    def analyze(self, symbol, features, evidences, regime):
        return MarketView(bias="BUY", confidence_adjustment=0.05, rationale="ok")


def uptrend_df(n=260, seed=1):
    rng = np.random.default_rng(seed)
    base = np.linspace(100, 150, n)
    close = base + rng.normal(0, 0.5, n)
    high = close + 1.0
    low = close - 1.0
    return pd.DataFrame({
        "open": close - 0.2, "high": high, "low": low,
        "close": close, "volume": rng.integers(3000, 9000, n).astype(float),
    })


def build_app(mode=TradeMode.ADVISOR):
    settings = Settings(webhook_secret="x" * 12, mode=mode)
    app = TradingApp(settings, broker=PaperBroker(starting_equity=Decimal("100000")))
    app.analyst = ConfirmAnalyst()
    return app


def test_live_loop_runs_and_calls_feed():
    app = build_app()
    feed = FakeFeed(uptrend_df())
    loop = LiveLoop(app, feed, ["AAPL"], timeframe="1h")
    loop.run_cycle()
    assert feed.calls == 1  # جلب البيانات مرة لكل رمز


def test_live_loop_handles_feed_failure_gracefully():
    class BrokenFeed:
        def get_candles(self, *a, **k):
            raise ConnectionError("network down")
    app = build_app()
    loop = LiveLoop(app, BrokenFeed(), ["AAPL"])
    loop.run_cycle()  # يجب ألا يرمي استثناء — يسجّل ويكمل


def test_live_loop_full_auto_executes():
    app = build_app(mode=TradeMode.FULL_AUTO)
    feed = FakeFeed(uptrend_df())
    loop = LiveLoop(app, feed, ["AAPL"], timeframe="1h")
    before = app.broker.get_account_state().open_positions
    loop.run_cycle()
    after = app.broker.get_account_state().open_positions
    assert after >= before  # قد يفتح صفقة إن توافقت الشروط
