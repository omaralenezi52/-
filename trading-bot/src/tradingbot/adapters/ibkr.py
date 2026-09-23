"""
محوّل Interactive Brokers (هيكل جاهز للربط بـ ib_insync).

IBKR توفّر API رسمياً قوياً للتنفيذ الآلي. هذا الملف يحدد الشكل الصحيح
للتكامل؛ يُكمَّل بالربط الفعلي عبر ib_insync عند تجهيز حساب TWS/Gateway.

نقاط أمان مضمّنة في التصميم:
- كل أمر يحمل client_order_id (Idempotency) لمنع التكرار.
- التنفيذ عبر أمر مركّب (bracket) لضمان وجود وقف خسارة دائماً.
"""
from __future__ import annotations

from ..domain.models import AccountState, TradePlan
from .base import BrokerAdapter, OrderResult


class IBKRAdapter(BrokerAdapter):
    supports_execution = True

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1) -> None:
        # المنفذ 7497 = Paper، 7496 = Live (ابدأ Paper دائماً)
        self.host = host
        self.port = port
        self.client_id = client_id
        self._ib = None  # يُربط بـ ib_insync.IB() عند التفعيل

    @property
    def name(self) -> str:
        return "ibkr"

    def connect(self) -> None:  # pragma: no cover - يتطلب TWS/Gateway حيّاً
        try:
            from ib_insync import IB  # استيراد كسول: اختياري حتى التفعيل
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ثبّت ib_insync لتفعيل التنفيذ عبر Interactive Brokers"
            ) from exc
        self._ib = IB()
        self._ib.connect(self.host, self.port, clientId=self.client_id)

    def get_account_state(self) -> AccountState:  # pragma: no cover - يتطلب اتصالاً
        raise NotImplementedError("يُكمَّل عبر self._ib.accountSummary() عند الربط")

    def place_bracket_order(self, plan: TradePlan, client_order_id: str) -> OrderResult:  # pragma: no cover
        raise NotImplementedError(
            "يُكمَّل عبر self._ib.bracketOrder(...) مع تمرير client_order_id"
        )
