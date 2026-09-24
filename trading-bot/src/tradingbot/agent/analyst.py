"""
عقدة المحلل الذكي (LLM Analyst) — تضيف طبقة الحكم والسياق فوق الأدلة الحتمية.

الفلسفة (مطابقة لكامل النظام): الـ LLM *مستشار* لا حاكم. يستقبل الأرقام
والأدلة الجاهزة (لا يحسبها بنفسه)، ويُرجع رأياً مهيكلاً:
- هل يؤكد الاتجاه أم يعارضه؟
- فيتو (veto): هل يوجد سبب سياقي لإلغاء الصفقة رغم توافق المؤشرات؟
- تعديل طفيف على الثقة + شرح نصّي مفسّر.

حاكم المخاطر (RiskEngine) يبقى الفيصل النهائي — حتى لو النموذج تحمّس،
لا صفقة تمر بدون موافقة المخاطر. وحتى لو فشل النموذج أو غاب المفتاح،
النظام يكمل بأمان برأي محايد (لا يعطّل التداول ولا يخترعه).
"""
from __future__ import annotations

import logging
from typing import Literal, Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger("tradingbot.analyst")

# النموذج الافتراضي — الأحدث والأكثر قدرة (يُغيَّر عبر الإعداد عند الحاجة)
DEFAULT_MODEL = "claude-opus-5"


class MarketView(BaseModel):
    """رأي المحلل المهيكل — مخرجات صارمة تمنع أخطاء الـ Parsing."""
    bias: Literal["BUY", "SELL", "NEUTRAL"] = Field(
        description="اتجاه رأي المحلل بعد قراءة السياق"
    )
    veto: bool = Field(
        default=False,
        description="True لإلغاء الصفقة رغم توافق المؤشرات (سبب سياقي خطر)",
    )
    confidence_adjustment: float = Field(
        default=0.0, ge=-0.3, le=0.3,
        description="تعديل طفيف على الثقة المجمّعة (بين -0.3 و +0.3)",
    )
    risk_flag: Literal["Low", "Medium", "High"] = Field(default="Medium")
    rationale: str = Field(default="", description="شرح موجز للقرار")

    @staticmethod
    def neutral(reason: str = "رأي محايد (تعذّر التحليل الذكي)") -> "MarketView":
        return MarketView(bias="NEUTRAL", veto=False,
                          confidence_adjustment=0.0, rationale=reason)


class Analyst(Protocol):
    """واجهة أي محلل — تسمح باستبدال Claude بمحلل وهمي في الاختبارات."""
    def analyze(self, symbol: str, features: dict,
                evidences: list, regime: str) -> MarketView: ...


SYSTEM_PROMPT = """أنت محلل أسواق مالية خبير داخل نظام تداول آلي.
مهمتك: مراجعة إشارة فنية *سبق حسابها* واتخاذ حكم سياقي — لا تحسب مؤشرات بنفسك.

قواعد صارمة:
- لا تعتمد على مؤشر واحد. وازن كل الأدلة معاً.
- إذا كان السعر يرتفع لكن RSI يظهر تشبعاً شديداً (>75) أو الحجم يضعف،
  اعتبرها احتمال مصيدة ثيران وضع veto=true أو bias=NEUTRAL.
- veto=true فقط عند خطر سياقي حقيقي (تشبع حاد، تعارض قوي، تقلب مفرط).
- كن محافظاً: عند الشك، NEUTRAL أفضل من إشارة خاطئة.
- confidence_adjustment صغير (±0.3 كحد أقصى) — أنت تعدّل لا تقرر من الصفر.
أعطِ حكمك بصيغة منظمة فقط."""


class ClaudeAnalyst:
    """محلل مبني على Claude عبر Anthropic SDK مع مخرجات مهيكلة."""

    def __init__(self, model: str = DEFAULT_MODEL, client=None) -> None:
        self.model = model
        self._client = client  # يُحقن للاختبار؛ وإلا يُنشأ كسولاً

    def _get_client(self):
        if self._client is None:
            import anthropic  # استيراد كسول (اختياري حتى التفعيل)
            self._client = anthropic.Anthropic()  # يقرأ ANTHROPIC_API_KEY من البيئة
        return self._client

    def analyze(self, symbol: str, features: dict,
                evidences: list, regime: str) -> MarketView:
        evidence_lines = "\n".join(
            f"- {e.name} ({e.side.value}, وزن {e.weight}): {e.detail}"
            for e in evidences
        ) or "لا أدلة"

        user_msg = (
            f"الرمز: {symbol}\n"
            f"نظام السوق: {regime}\n"
            f"المؤشرات: السعر={features.get('close')}, RSI={features.get('rsi'):.1f}, "
            f"EMA20={features.get('ema_fast'):.2f}, EMA50={features.get('ema_slow'):.2f}, "
            f"ATR={features.get('atr'):.2f}, الحجم={features.get('volume')}\n"
            f"الأدلة المكتشفة:\n{evidence_lines}\n\n"
            f"راجع هذه المعطيات وأعطِ حكمك."
        )

        try:
            client = self._get_client()
            response = client.messages.parse(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                output_format=MarketView,
            )
            view = response.parsed_output
            if view is None:
                return MarketView.neutral("النموذج لم يُرجع رأياً صالحاً")
            return view
        except Exception:
            # فشل الشبكة/المفتاح/التحليل لا يوقف النظام — نكمل برأي محايد
            logger.exception("فشل تحليل Claude — المتابعة برأي محايد")
            return MarketView.neutral()


class NeutralAnalyst:
    """محلل محايد — بديل آمن عند غياب مفتاح API أو لتعطيل الذكاء."""
    def analyze(self, symbol: str, features: dict,
                evidences: list, regime: str) -> MarketView:
        return MarketView.neutral("الذكاء غير مُفعّل (لا مفتاح API)")


def build_analyst(api_key: str | None, model: str = DEFAULT_MODEL) -> Analyst:
    """يختار المحلل المناسب حسب توفّر المفتاح."""
    if api_key:
        return ClaudeAnalyst(model=model)
    return NeutralAnalyst()
