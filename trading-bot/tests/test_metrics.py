"""اختبارات مقاييس الأداء — بمدخلات معروفة ومخرجات متوقعة بدقة."""
import math

from tradingbot.backtest.metrics import (
    build_report,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)


def test_max_drawdown_basic():
    # قمة 120 ثم هبوط إلى 90 ⇒ تراجع = (120-90)/120 = 25%
    curve = [100, 120, 90, 110]
    assert math.isclose(max_drawdown(curve), 25.0, rel_tol=1e-6)


def test_max_drawdown_no_decline():
    assert max_drawdown([100, 110, 120]) == 0.0


def test_max_drawdown_empty():
    assert max_drawdown([]) == 0.0


def test_sharpe_zero_when_no_volatility():
    assert sharpe_ratio([0.05, 0.05, 0.05]) == 0.0


def test_sharpe_positive_for_positive_returns():
    assert sharpe_ratio([0.01, 0.02, 0.03, -0.01]) > 0


def test_sortino_ignores_upside_volatility():
    # كل العوائد موجبة ⇒ لا انحراف خسائر ⇒ 0
    assert sortino_ratio([0.01, 0.02, 0.03]) == 0.0


def test_build_report_profit_factor_and_win_rate():
    # 3 صفقات: +100, +50, -60
    pnls = [100.0, 50.0, -60.0]
    returns = [0.10, 0.05, -0.06]
    equity = [1000, 1100, 1150, 1090]
    rep = build_report(pnls, returns, equity, initial_equity=1000)

    assert rep.num_trades == 3
    assert math.isclose(rep.win_rate, 2 / 3, rel_tol=1e-6)
    # عامل الربح = 150 / 60 = 2.5
    assert math.isclose(rep.profit_factor, 2.5, rel_tol=1e-6)
    assert math.isclose(rep.expectancy, 30.0, rel_tol=1e-6)  # (100+50-60)/3
    assert math.isclose(rep.total_return_pct, 9.0, rel_tol=1e-6)  # (1090-1000)/1000


def test_build_report_all_wins_infinite_profit_factor():
    rep = build_report([10.0, 20.0], [0.1, 0.2], [100, 110, 130], 100)
    assert rep.profit_factor == float("inf")


def test_build_report_no_trades():
    rep = build_report([], [], [1000], initial_equity=1000)
    assert rep.num_trades == 0
    assert rep.win_rate == 0.0
    assert rep.total_return_pct == 0.0
