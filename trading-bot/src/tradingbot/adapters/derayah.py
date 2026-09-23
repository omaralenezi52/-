"""
محوّل دراية المالية — وضع "إشعار فقط" (notify-only).

دراية (كأغلب الوسطاء المحليين) لا توفّر API رسمياً للتنفيذ الآلي.
لذلك هذا المحوّل يجلب/يستقبل حالة الحساب يدوياً، لكنه يرفض التنفيذ
الآلي بوضوح. البوت في هذه الحالة يرسل التوصية على تليجرام والمستخدم
ينفّذ يدوياً في تطبيق دراية.

⚠️ لا تحاول محاكاة المتصفح/التطبيق للتنفيذ: هش، يخالف شروط الاستخدام،
وخطر على أموال العميل.
"""
from __future__ import annotations

from decimal import Decimal

from ..domain.models import AccountState, TradePlan
from .base import BrokerAdapter, NotSupportedError, OrderResult


class DerayahAdapter(BrokerAdapter):
    supports_execution = False

    def __init__(self, equity: Decimal, cash: Decimal) -> None:
        # تُدخل يدوياً لأن لا API لجلبها آلياً
        self._equity = equity
        self._cash = cash

    @property
    def name(self) -> str:
        return "derayah"

    def get_account_state(self) -> AccountState:
        return AccountState(equity=self._equity, cash_available=self._cash)

    def place_bracket_order(self, plan: TradePlan, client_order_id: str) -> OrderResult:
        raise NotSupportedError(
            "دراية لا تدعم التنفيذ الآلي — استخدم وضع الإشعار وننفّذ يدوياً"
        )
