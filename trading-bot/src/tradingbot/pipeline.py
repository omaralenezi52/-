"""
خط المعالجة (Pipeline) — ترابط القرارات من الإشارة إلى التوصية.

التسلسل (كل خطوة تحكم التي بعدها):
  1. DecisionEngine  → توافق الأدلة + نظام السوق (قرار أولي + ثقة).
  2. اشتقاق المستويات (وقف/هدف) من ATR أو نسب افتراضية.
  3. RiskEngine (الحاكم) → يعتمد أو يرفض، ويحسب الحجم.
  4. بناء التوصية النهائية بالأرقام.

طبقة الـ LLM (لاحقاً) تُحقن كخطوة إثراء بين 1 و3 لإضافة السياق
والتحليل النصّي، لكنها لا تتجاوز حاكم المخاطر إطلاقاً.
"""
from __future__ import annotations

from decimal import Decimal

from .domain.decision import DecisionEngine, Evidence
from .domain.models import (
    AccountState,
    Decision,
    Recommendation,
    Side,
    Signal,
)
from .domain.risk import RiskEngine


def derive_levels(signal: Signal, rr_target: Decimal = Decimal("2")) -> tuple[Decimal, Decimal]:
    """
    يشتق وقف الخسارة والهدف. يفضّل ATR إن توفّر (أدق)، وإلا نسبة افتراضية.
    الهدف = مسافة الوقف × rr_target لضمان نسبة عائد/مخاطرة جيدة.
    """
    entry = signal.price
    atr = signal.indicators.get("atr")
    if atr is not None:
        stop_dist = Decimal(str(atr)) * Decimal("1.5")
    else:
        stop_dist = entry * Decimal("0.02")  # 2% افتراضياً

    reward_dist = stop_dist * rr_target
    if signal.side == Side.BUY:
        return (entry - stop_dist, entry + reward_dist)
    return (entry + stop_dist, entry - reward_dist)


def run_pipeline(
    signal: Signal,
    evidences: list[Evidence],
    account: AccountState,
    decision_engine: DecisionEngine,
    risk_engine: RiskEngine,
    rationale: str = "",
) -> Recommendation:
    """يمرّر الإشارة عبر كامل السلسلة ويُنتج توصية نهائية."""

    # 1) توافق الأدلة
    conf = decision_engine.evaluate(signal, evidences)
    if conf.decision == Decision.WAIT:
        return Recommendation(
            symbol=signal.symbol,
            decision=Decision.WAIT,
            confidence=conf.confidence,
            regime=conf.regime,
            reasons=conf.reasons,
            rationale=rationale,
        )

    # 2) اشتقاق المستويات
    stop_loss, take_profit = derive_levels(signal)

    # 3) حاكم المخاطر (البوابة الحاسمة)
    risk = risk_engine.evaluate(
        signal=signal,
        stop_loss=stop_loss,
        take_profit=take_profit,
        account=account,
        confidence=conf.confidence,
    )
    if not risk.approved:
        return Recommendation(
            symbol=signal.symbol,
            decision=Decision.REJECT,
            confidence=conf.confidence,
            regime=conf.regime,
            reasons=conf.reasons,
            rationale=rationale,
            rejection_reason=risk.reason,
        )

    # 4) توصية قابلة للتنفيذ
    return Recommendation(
        symbol=signal.symbol,
        decision=conf.decision,
        confidence=conf.confidence,
        regime=conf.regime,
        plan=risk.plan,
        reasons=conf.reasons,
        rationale=rationale,
    )


def run_pipeline_with_analyst(
    signal: Signal,
    evidences: list[Evidence],
    account: AccountState,
    decision_engine: DecisionEngine,
    risk_engine: RiskEngine,
    analyst,
    features: dict | None = None,
) -> Recommendation:
    """
    نسخة كاملة مع طبقة الذكاء: تُدرج حكم المحلل (LLM) بين التوافق والمخاطر.

    التسلسل: توافق الأدلة → المحلل (فيتو + تعديل ثقة + شرح) → حاكم المخاطر.
    المحلل *مستشار*: يقدر يخفض/يرفع الثقة أو يعترض (veto)، لكن حاكم المخاطر
    يبقى الفيصل النهائي، وأي فشل في المحلل يكمل النظام بأمان.
    """
    # 1) توافق الأدلة الحتمي
    conf = decision_engine.evaluate(signal, evidences)
    if conf.decision == Decision.WAIT:
        return Recommendation(
            symbol=signal.symbol, decision=Decision.WAIT,
            confidence=conf.confidence, regime=conf.regime, reasons=conf.reasons,
        )

    # 2) حكم المحلل الذكي (لا يحسب أرقاماً — يقرأ ويحكم)
    view = analyst.analyze(
        symbol=signal.symbol,
        features=features or signal.indicators,
        evidences=evidences,
        regime=conf.regime.value,
    )

    # فيتو المحلل: سبب سياقي لإلغاء الصفقة رغم توافق المؤشرات
    if view.veto or view.bias == "NEUTRAL":
        return Recommendation(
            symbol=signal.symbol, decision=Decision.WAIT,
            confidence=conf.confidence, regime=conf.regime, reasons=conf.reasons,
            rationale=view.rationale,
            rejection_reason="فيتو المحلل" if view.veto else None,
        )

    # تعديل الثقة برأي المحلل (محصور بين 0 و 1)
    adjusted_conf = max(0.0, min(1.0, conf.confidence + view.confidence_adjustment))

    # 3) اشتقاق المستويات
    stop_loss, take_profit = derive_levels(signal)

    # 4) حاكم المخاطر (الفيصل النهائي)
    risk = risk_engine.evaluate(
        signal=signal, stop_loss=stop_loss, take_profit=take_profit,
        account=account, confidence=adjusted_conf,
    )
    if not risk.approved:
        return Recommendation(
            symbol=signal.symbol, decision=Decision.REJECT,
            confidence=adjusted_conf, regime=conf.regime, reasons=conf.reasons,
            rationale=view.rationale, rejection_reason=risk.reason,
        )

    # 5) توصية نهائية مع شرح المحلل
    return Recommendation(
        symbol=signal.symbol,
        decision=conf.decision,
        confidence=adjusted_conf,
        regime=conf.regime,
        plan=risk.plan,
        reasons=conf.reasons,
        rationale=view.rationale,
    )
