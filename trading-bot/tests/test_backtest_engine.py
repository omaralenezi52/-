"""اختبارات محرك الاختبار التاريخي — المكانيكا ومنع Look-ahead."""
import numpy as np
import pandas as pd

from tradingbot.backtest.engine import Backtester
from tradingbot.domain.models import Side


def make_trend_df(n=400, direction="up", seed=7):
    rng = np.random.default_rng(seed)
    if direction == "up":
        base = np.linspace(100, 200, n)
    else:
        base = np.linspace(200, 100, n)
    noise = rng.normal(0, 1.0, n)
    close = base + noise
    high = close + np.abs(rng.normal(0, 0.8, n)) + 0.5
    low = close - np.abs(rng.normal(0, 0.8, n)) - 0.5
    open_ = close - rng.normal(0, 0.3, n)
    volume = rng.integers(1000, 6000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


def test_backtest_runs_and_produces_report():
    bt = Backtester(warmup=200)
    result = bt.run(make_trend_df())
    assert result.report.num_trades >= 0
    assert len(result.equity_curve) >= 1
    assert isinstance(result.summary(), str)


def test_no_lookahead_exit_after_entry():
    """كل صفقة مغلقة يجب أن يكون خروجها بعد دخولها (لا نظر للمستقبل)."""
    bt = Backtester(warmup=200)
    result = bt.run(make_trend_df())
    for t in result.trades:
        if t.is_closed:
            assert t.exit_index >= t.entry_index


def test_trades_respect_side_and_levels():
    bt = Backtester(warmup=200)
    result = bt.run(make_trend_df(direction="up"))
    for t in result.trades:
        if t.side == Side.BUY:
            assert t.stop_loss < t.entry_price < t.take_profit
        else:
            assert t.take_profit < t.entry_price < t.stop_loss


def test_equity_curve_consistent_with_trades():
    bt = Backtester(warmup=200, initial_equity=100000)
    result = bt.run(make_trend_df())
    # رأس المال النهائي = المبدئي + مجموع أرباح الصفقات
    expected = 100000 + sum(t.pnl for t in result.trades)
    assert abs(result.equity_curve[-1] - expected) < 1e-6


def test_report_metrics_within_valid_ranges():
    bt = Backtester(warmup=200)
    rep = bt.run(make_trend_df()).report
    assert 0.0 <= rep.win_rate <= 1.0
    assert rep.max_drawdown_pct >= 0.0
