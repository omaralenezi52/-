"""محرك الاختبار التاريخي ومقاييس الأداء."""
from .engine import Backtester, BacktestResult, Trade
from .metrics import PerformanceReport, build_report, max_drawdown, sharpe_ratio, sortino_ratio

__all__ = [
    "Backtester", "BacktestResult", "Trade", "PerformanceReport",
    "build_report", "max_drawdown", "sharpe_ratio", "sortino_ratio",
]
