"""
حاكم المخاطر (RiskEngine) — قلب النظام والطبقة الحتمية التي تحكم كل قرار.

المبدأ: الـ LLM يقترح، لكن هذا المحرك (كود بايثون بحت، بدون أي عشوائية)
هو من يقرر: هل يُسمح بالصفقة؟ وبأي حجم؟

كل قرار تداول *يجب* أن يمر من هنا. لا استثناءات. هذه هي "نقطة الخطر"
المركزية التي تمنع الانهيار: تحسب الحجم من مسافة الوقف، وترفض أي صفقة
تخالف حدود المخاطر (نسبة العائد، الخسارة اليومية، الحد الأقصى للصفقات).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from .models import AccountState, Decision, Side, Signal, TradePlan


@dataclass(frozen=True)
class RiskLimits:
    """
    حدود المخاطر القابلة للضبط. القيم الافتراضية محافظة عمداً
    لأن حماية رأس المال أهم من تعظيم الربح.
    """
    # أقصى نسبة من رأس المال يُخاطر بها في صفقة واحدة
    max_risk_per_trade_pct: Decimal = Decimal("0.01")   # 1%
    # أقصى خسارة يومية — عند تجاوزها يتوقف التداول لليوم
    max_daily_loss_pct: Decimal = Decimal("0.03")       # 3%
    # الحد الأدنى المقبول لنسبة العائد/المخاطرة
    min_risk_reward: Decimal = Decimal("1.5")
    # أقصى عدد صفقات مفتوحة في وقت واحد
    max_open_positions: int = 5
    # أقصى نسبة من رأس المال تُخصّص لصفقة واحدة (حد الانكشاف)
    max_position_pct: Decimal = Decimal("0.25")         # 25%
    # الحد الأدنى للثقة المجمّعة لقبول الصفقة
    min_confidence: float = 0.65

    def __post_init__(self) -> None:
        if self.max_risk_per_trade_pct <= 0 or self.max_risk_per_trade_pct > Decimal("0.1"):
            raise ValueError("max_risk_per_trade_pct يجب أن تكون بين 0 و 10%")
        if self.min_risk_reward < 1:
            raise ValueError("min_risk_reward يجب ألا تقل عن 1")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions يجب أن يكون 1 على الأقل")


@dataclass(frozen=True)
class RiskDecision:
    """نتيجة تقييم حاكم المخاطر."""
    approved: bool
    plan: TradePlan | None = None
    reason: str = ""


class RiskEngine:
    """
    حاكم المخاطر. يأخذ إشارة + مستويات (وقف/هدف) + حالة الحساب،
    ويُرجع خطة صفقة معتمدة أو رفضاً مع السبب.
    """

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def evaluate(
        self,
        signal: Signal,
        stop_loss: Decimal,
        take_profit: Decimal,
        account: AccountState,
        confidence: float,
    ) -> RiskDecision:
        """
        التقييم الكامل. الترتيب مقصود: نفحص البوابات الأرخص/الأخطر أولاً
        (الحالة العامة) قبل حساب الحجم.
        """
        L = self.limits

        # --- بوابة 1: توقف الخسارة اليومي (Circuit Breaker) ---
        # خسارة اليوم تُخزّن كقيمة سالبة. نقارن حجمها بالحد.
        max_daily_loss = (account.equity * L.max_daily_loss_pct).copy_abs()
        if account.realized_pnl_today <= -max_daily_loss:
            return RiskDecision(
                False,
                reason=f"تجاوز حد الخسارة اليومي ({L.max_daily_loss_pct:.1%})؛ التداول متوقف لليوم",
            )

        # --- بوابة 2: عدد الصفقات المفتوحة ---
        if account.open_positions >= L.max_open_positions:
            return RiskDecision(
                False,
                reason=f"بلغ الحد الأقصى للصفقات المفتوحة ({L.max_open_positions})",
            )

        # --- بوابة 3: الثقة المجمّعة ---
        if confidence < L.min_confidence:
            return RiskDecision(
                False,
                reason=f"الثقة {confidence:.0%} أقل من الحد الأدنى {L.min_confidence:.0%}",
            )

        # --- بوابة 4: سلامة المستويات ---
        entry = signal.price
        if stop_loss <= 0 or take_profit <= 0:
            return RiskDecision(False, reason="مستويات الوقف/الهدف غير صالحة")

        # الوقف لازم يكون في الجهة الصحيحة (وإلا لا معنى للمخاطرة)
        if signal.side == Side.BUY and not (stop_loss < entry < take_profit):
            return RiskDecision(False, reason="ترتيب المستويات غير منطقي لصفقة شراء")
        if signal.side == Side.SELL and not (take_profit < entry < stop_loss):
            return RiskDecision(False, reason="ترتيب المستويات غير منطقي لصفقة بيع")

        # --- بوابة 5: نسبة العائد/المخاطرة ---
        risk_per_unit = (entry - stop_loss).copy_abs()
        reward_per_unit = (take_profit - entry).copy_abs()
        if risk_per_unit == 0:
            return RiskDecision(False, reason="مسافة الوقف صفر — لا يمكن حساب الحجم")

        rr = (reward_per_unit / risk_per_unit).quantize(Decimal("0.01"))
        if rr < L.min_risk_reward:
            return RiskDecision(
                False,
                reason=f"نسبة العائد/المخاطرة {rr} أقل من الحد الأدنى {L.min_risk_reward}",
            )

        # --- حساب الحجم: من مسافة الوقف، لا من مبلغ عشوائي ---
        risk_budget = account.equity * L.max_risk_per_trade_pct
        raw_qty = risk_budget / risk_per_unit
        quantity = raw_qty.quantize(Decimal("1"), rounding=ROUND_DOWN)  # عقود صحيحة

        if quantity < 1:
            return RiskDecision(
                False,
                reason="ميزانية المخاطرة لا تكفي لعقد واحد بمسافة الوقف الحالية",
            )

        # --- بوابة 6: حد الانكشاف + النقد المتاح ---
        position_value = quantity * entry
        if position_value > account.equity * L.max_position_pct:
            # نقلّص الحجم ليحترم حد الانكشاف بدل الرفض الكامل
            max_qty_by_exposure = (
                (account.equity * L.max_position_pct) / entry
            ).quantize(Decimal("1"), rounding=ROUND_DOWN)
            quantity = min(quantity, max_qty_by_exposure)

        if quantity < 1:
            return RiskDecision(False, reason="حد الانكشاف لا يسمح بعقد واحد")

        position_value = quantity * entry
        if position_value > account.cash_available:
            return RiskDecision(
                False,
                reason="النقد المتاح لا يكفي لفتح الصفقة بالحجم المحسوب",
            )

        actual_risk = (quantity * risk_per_unit).quantize(Decimal("0.01"))
        plan = TradePlan(
            symbol=signal.symbol,
            side=signal.side,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            quantity=quantity,
            risk_amount=actual_risk,
            risk_reward_ratio=rr,
        )
        return RiskDecision(True, plan=plan, reason="اعتُمدت ضمن حدود المخاطر")
