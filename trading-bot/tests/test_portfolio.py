"""اختبار إدارة مخاطر المحفظة."""
from decimal import Decimal

from tradingbot.domain.portfolio import (
    OpenPosition,
    PortfolioLimits,
    PortfolioManager,
)


def test_approves_when_empty():
    pm = PortfolioManager()
    d = pm.check("AAPL", Decimal("10000"), Decimal("100000"), [])
    assert d.approved


def test_rejects_total_exposure():
    pm = PortfolioManager(PortfolioLimits(max_total_exposure_pct=Decimal("0.5")))
    positions = [OpenPosition("JPM", Decimal("45000"))]
    # 45k موجود + 10k جديد = 55k / 100k = 55% > 50%
    d = pm.check("XOM", Decimal("10000"), Decimal("100000"), positions)
    assert not d.approved and "التعرّض" in d.reason


def test_rejects_same_symbol():
    pm = PortfolioManager()
    positions = [OpenPosition("AAPL", Decimal("5000"))]
    d = pm.check("AAPL", Decimal("5000"), Decimal("100000"), positions)
    assert not d.approved and "AAPL" in d.reason


def test_rejects_same_sector_correlation():
    pm = PortfolioManager(PortfolioLimits(max_per_sector=2))
    # AAPL و MSFT و NVDA كلها tech — الثالثة تُرفض
    positions = [OpenPosition("AAPL", Decimal("5000")),
                 OpenPosition("MSFT", Decimal("5000"))]
    d = pm.check("NVDA", Decimal("5000"), Decimal("100000"), positions)
    assert not d.approved and "قطاع" in d.reason


def test_allows_different_sector():
    pm = PortfolioManager(PortfolioLimits(max_per_sector=2))
    positions = [OpenPosition("AAPL", Decimal("5000")),
                 OpenPosition("MSFT", Decimal("5000"))]
    # JPM قطاع مختلف (finance) ⇒ مقبول
    d = pm.check("JPM", Decimal("5000"), Decimal("100000"), positions)
    assert d.approved
