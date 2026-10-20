"""
إدارة المخاطر على مستوى المحفظة (Portfolio Risk) — طبقة احترافية.

حاكم المخاطر (RiskEngine) يحكم الصفقة الواحدة. هذه الطبقة تحكم المحفظة ككل:
- أقصى تعرّض إجمالي (مجموع قيمة الصفقات / رأس المال).
- أقصى عدد صفقات في نفس الرمز.
- أقصى عدد صفقات في مجموعة مترابطة (نفس القطاع) — يمنع المخاطرة المضاعفة
  حين تتحرك الأسهم المترابطة معاً.

المبدأ المؤسسي: لا تكفي سلامة كل صفقة؛ يجب أن تكون المحفظة ككل متوازنة.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


# تصنيف قطاعي مبسّط للترابط (يُوسّع أو يُستبدل بمصفوفة ارتباط فعلية)
SECTOR_MAP = {
    "AAPL": "tech", "MSFT": "tech", "NVDA": "tech", "GOOGL": "tech",
    "META": "tech", "AMZN": "tech", "TSLA": "auto",
    "JPM": "finance", "BAC": "finance", "GS": "finance",
    "XOM": "energy", "CVX": "energy",
    "SPY": "index", "QQQ": "index",
}


@dataclass(frozen=True)
class PortfolioLimits:
    max_total_exposure_pct: Decimal = Decimal("0.60")  # أقصى 60% من رأس المال منكشف
    max_per_symbol: int = 1                             # صفقة واحدة لكل رمز
    max_per_sector: int = 2                             # أقصى صفقتين في قطاع واحد


@dataclass
class OpenPosition:
    symbol: str
    market_value: Decimal

    @property
    def sector(self) -> str:
        return SECTOR_MAP.get(self.symbol.upper(), "other")


@dataclass(frozen=True)
class PortfolioDecision:
    approved: bool
    reason: str = ""


class PortfolioManager:
    """يفحص صفقة مقترحة مقابل حالة المحفظة الحالية."""

    def __init__(self, limits: PortfolioLimits | None = None) -> None:
        self.limits = limits or PortfolioLimits()

    def check(
        self,
        symbol: str,
        new_value: Decimal,
        equity: Decimal,
        open_positions: list[OpenPosition],
    ) -> PortfolioDecision:
        L = self.limits
        sector = SECTOR_MAP.get(symbol.upper(), "other")

        # 1) حد التعرّض الإجمالي
        current_exposure = sum((p.market_value for p in open_positions), Decimal("0"))
        if equity > 0:
            projected = (current_exposure + new_value) / equity
            if projected > L.max_total_exposure_pct:
                return PortfolioDecision(
                    False,
                    f"التعرّض الإجمالي {projected:.0%} يتجاوز الحد {L.max_total_exposure_pct:.0%}",
                )

        # 2) حد الرمز الواحد
        same_symbol = sum(1 for p in open_positions if p.symbol.upper() == symbol.upper())
        if same_symbol >= L.max_per_symbol:
            return PortfolioDecision(False, f"صفقة مفتوحة بالفعل على {symbol}")

        # 3) حد القطاع (الترابط)
        same_sector = sum(1 for p in open_positions if p.sector == sector)
        if same_sector >= L.max_per_sector:
            return PortfolioDecision(
                False,
                f"بلغ حد الصفقات في قطاع {sector} ({L.max_per_sector}) — تجنّب المخاطرة المترابطة",
            )

        return PortfolioDecision(True, "مقبول على مستوى المحفظة")
