"""
النماذج الأساسية (Domain Models) لنظام التداول.

كل الأنواع هنا "بيانات نقية" (بدون منطق منصة أو LLM) عشان تكون:
- قابلة للاختبار 100%.
- مشتركة بين كل الطبقات (المحرك، الوكلاء، المنصات، الإشعارات).

ملاحظة مالية مهمة: نستخدم Decimal لكل الأسعار والكميات والأرصدة
لتجنّب أخطاء التقريب في float التي تتراكم في العمليات المالية.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional


class Side(str, Enum):
    """اتجاه الصفقة."""
    BUY = "BUY"
    SELL = "SELL"


class Decision(str, Enum):
    """القرار النهائي لمحرك التداول."""
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"      # لا توجد فرصة كافية الآن
    REJECT = "REJECT"  # رُفضت من حاكم المخاطر (RiskEngine)


class MarketRegime(str, Enum):
    """نظام السوق الحالي — يحدد أي منطق تحليل يُطبّق."""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"          # عرضي متذبذب
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class TradeMode(str, Enum):
    """وضع تشغيل البوت (يحدد مدى الأتمتة)."""
    ADVISOR = "ADVISOR"        # توصية فقط، التنفيذ يدوي
    SEMI_AUTO = "SEMI_AUTO"    # ينتظر موافقة المستخدم قبل التنفيذ
    FULL_AUTO = "FULL_AUTO"    # ينفّذ تلقائياً ضمن حدود المخاطر


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Signal:
    """
    الإشارة الخام الواردة من مصدر خارجي (مثل TradingView Webhook).

    هذه إشارة "مرشّحة" وليست قراراً — لا يُتداول عليها قبل أن تمر
    على محرك القرار وحاكم المخاطر.
    """
    symbol: str
    side: Side
    price: Decimal
    source: str = "unknown"
    # ثقة المصدر نفسه بالإشارة (0..1)، اختيارية
    source_confidence: Optional[float] = None
    # مؤشرات محسوبة مسبقاً (من TradingView أو pandas-ta)
    indicators: dict = field(default_factory=dict)
    timeframe: str = "1h"
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("سعر الإشارة يجب أن يكون أكبر من صفر")
        if self.source_confidence is not None and not (0.0 <= self.source_confidence <= 1.0):
            raise ValueError("source_confidence يجب أن تكون بين 0 و 1")


@dataclass(frozen=True)
class AccountState:
    """
    لقطة عن حالة الحساب — مصدر الحقيقة للمخاطر.
    تُجلب من المنصة، لا تُخمّن.
    """
    equity: Decimal                 # القيمة الكلية للحساب
    cash_available: Decimal         # النقد المتاح للتداول
    open_positions: int = 0
    realized_pnl_today: Decimal = Decimal("0")  # أرباح/خسائر اليوم المحققة

    def __post_init__(self) -> None:
        if self.equity < 0 or self.cash_available < 0:
            raise ValueError("قيم الحساب لا يمكن أن تكون سالبة")


@dataclass(frozen=True)
class TradePlan:
    """
    خطة صفقة مكتملة بالأرقام — نتيجة محرك القرار قبل عرضها/تنفيذها.
    """
    symbol: str
    side: Side
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    quantity: Decimal
    risk_amount: Decimal            # المبلغ المخاطر به (بالعملة)
    risk_reward_ratio: Decimal      # نسبة العائد/المخاطرة

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("الكمية يجب أن تكون أكبر من صفر")
        # تحقّق منطقي: الوقف في الجهة الصحيحة
        if self.side == Side.BUY and self.stop_loss >= self.entry:
            raise ValueError("في الشراء، وقف الخسارة يجب أن يكون أقل من الدخول")
        if self.side == Side.SELL and self.stop_loss <= self.entry:
            raise ValueError("في البيع، وقف الخسارة يجب أن يكون أعلى من الدخول")


@dataclass(frozen=True)
class Recommendation:
    """
    التوصية النهائية التي تُرسل للمستخدم (تليجرام) أو تُنفّذ.
    تجمع القرار + الأرقام + شرح الذكاء + تقييم المخاطر.
    """
    symbol: str
    decision: Decision
    confidence: float                       # ثقة مجمّعة 0..1
    regime: MarketRegime
    plan: Optional[TradePlan] = None        # موجودة فقط عند BUY/SELL
    rationale: str = ""                     # شرح نصّي (من الـ LLM)
    reasons: list = field(default_factory=list)  # أدلة التوافق (Confluence)
    rejection_reason: Optional[str] = None  # سبب الرفض إن وُجد
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_actionable(self) -> bool:
        return self.decision in (Decision.BUY, Decision.SELL) and self.plan is not None
