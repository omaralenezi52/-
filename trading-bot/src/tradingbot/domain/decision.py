"""
محرك القرار (Decision Engine) — ترابط القرارات وتوافق الأدلة (Confluence).

الفكرة التي تصنع "الخبير": لا نعتمد على دليل واحد. نجمع عدة أدلة مستقلة
(اتجاه، زخم، حجم، مشاعر...) كل منها يعطي وزناً، والقرار يتطلب توافقاً
كافياً. صفقة بدليل واحد = تجاهل.

هذا المحرك حتمي (بدون LLM) ويُنتج ثقة قابلة للتفسير. طبقة الـ LLM (لاحقاً)
تضيف السياق فوق هذه النتيجة، لكن لا تلغي منطق التوافق.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .models import Decision, MarketRegime, Side, Signal


@dataclass(frozen=True)
class Evidence:
    """دليل واحد يدعم أو يعارض اتجاهاً معيّناً."""
    name: str
    side: Side              # الاتجاه الذي يدعمه هذا الدليل
    weight: float           # 0..1 وزن أهمية الدليل
    detail: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError("وزن الدليل يجب أن يكون بين 0 و 1")


@dataclass(frozen=True)
class ConfluenceResult:
    decision: Decision
    confidence: float
    regime: MarketRegime
    reasons: list = field(default_factory=list)   # الأدلة المتوافقة


class DecisionEngine:
    """
    يوازن الأدلة ويحدد نظام السوق، ثم يُنتج قراراً أولياً بثقة مفسّرة.
    """

    def __init__(self, min_agreeing: int = 3) -> None:
        # الحد الأدنى لعدد الأدلة المتوافقة لاعتبار الفرصة قائمة
        self.min_agreeing = min_agreeing

    def detect_regime(self, indicators: dict) -> MarketRegime:
        """
        كشف نظام السوق من المؤشرات (EMA، ADX، ATR...).
        يعتمد على قيم محسوبة مسبقاً؛ غيابها يعطي UNKNOWN بأمان.
        """
        adx = indicators.get("adx")
        ema_fast = indicators.get("ema_fast")
        ema_slow = indicators.get("ema_slow")

        if adx is not None and float(adx) < 20:
            return MarketRegime.RANGING
        if ema_fast is not None and ema_slow is not None:
            if float(ema_fast) > float(ema_slow):
                return MarketRegime.TRENDING_UP
            return MarketRegime.TRENDING_DOWN
        return MarketRegime.UNKNOWN

    def evaluate(self, signal: Signal, evidences: list[Evidence]) -> ConfluenceResult:
        """
        يجمع الأدلة إلى قرار. الثقة = صافي الأوزان المؤيدة / إجمالي الأوزان.
        """
        regime = self.detect_regime(signal.indicators)

        buy_weight = sum(e.weight for e in evidences if e.side == Side.BUY)
        sell_weight = sum(e.weight for e in evidences if e.side == Side.SELL)
        total_weight = buy_weight + sell_weight

        if total_weight == 0:
            return ConfluenceResult(Decision.WAIT, 0.0, regime, [])

        if buy_weight >= sell_weight:
            side, dominant, agreeing = Side.BUY, buy_weight, [
                e for e in evidences if e.side == Side.BUY
            ]
        else:
            side, dominant, agreeing = Side.SELL, sell_weight, [
                e for e in evidences if e.side == Side.SELL
            ]

        confidence = round(dominant / total_weight, 4)

        # شرط التوافق: يجب أن يتفق عدد كافٍ من الأدلة، وأن يوافق اتجاه الإشارة
        if len(agreeing) < self.min_agreeing or side != signal.side:
            return ConfluenceResult(
                Decision.WAIT,
                confidence,
                regime,
                [e.name for e in agreeing],
            )

        decision = Decision.BUY if side == Side.BUY else Decision.SELL
        reasons = [f"{e.name}: {e.detail}".strip(": ") for e in agreeing]
        return ConfluenceResult(decision, confidence, regime, reasons)
