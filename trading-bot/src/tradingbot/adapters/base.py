"""
واجهة المنصة المجرّدة (BrokerAdapter).

الهدف: عزل بقية النظام عن أي منصة معينة. تبديل المنصة = تبديل Adapter
واحد، دون لمس محرك القرار أو المخاطر أو الإشعارات.

- المنصات التي تدعم API تنفيذ (مثل Interactive Brokers) تطبّق place_order.
- المنصات بلا API تنفيذ (مثل دراية) ترفع NotSupportedError وتعمل
  في وضع "إشعار فقط" (notify-only).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.models import AccountState, TradePlan


class NotSupportedError(NotImplementedError):
    """تُرفع عندما لا تدعم المنصة عملية معينة (مثل التنفيذ الآلي)."""


class OrderResult:
    def __init__(self, order_id: str, status: str, detail: str = "") -> None:
        self.order_id = order_id
        self.status = status
        self.detail = detail


class BrokerAdapter(ABC):
    """العقد الموحّد لأي منصة."""

    #: هل تدعم هذه المنصة التنفيذ الآلي؟
    supports_execution: bool = False

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def get_account_state(self) -> AccountState:
        """يجلب حالة الحساب الحقيقية — مصدر الحقيقة للمخاطر."""

    @abstractmethod
    def place_bracket_order(self, plan: TradePlan, client_order_id: str) -> OrderResult:
        """
        يرسل أمراً مركباً (دخول + وقف + هدف) بشكل ذرّي.

        client_order_id: مفتاح تفرّد (Idempotency) يمنع تكرار الأمر
        إذا انقطع الرد وأُعيدت المحاولة.
        """
