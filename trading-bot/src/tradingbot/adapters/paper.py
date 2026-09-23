"""
منصة ورقية (Paper) للاختبار — تحاكي حساباً بلا مال حقيقي.

تُستخدم في التطوير والاختبار وقياس الأداء قبل أي حساب حقيقي.
تحترم مفتاح التفرّد (Idempotency) حتى لا تُنشئ أمرين لنفس المفتاح.
"""
from __future__ import annotations

from decimal import Decimal

from ..domain.models import AccountState, TradePlan
from .base import BrokerAdapter, OrderResult


class PaperBroker(BrokerAdapter):
    supports_execution = True

    def __init__(self, starting_equity: Decimal = Decimal("100000")) -> None:
        self._equity = starting_equity
        self._cash = starting_equity
        self._open_positions = 0
        self._pnl_today = Decimal("0")
        self._orders: dict[str, OrderResult] = {}  # idempotency store

    @property
    def name(self) -> str:
        return "paper"

    def get_account_state(self) -> AccountState:
        return AccountState(
            equity=self._equity,
            cash_available=self._cash,
            open_positions=self._open_positions,
            realized_pnl_today=self._pnl_today,
        )

    def place_bracket_order(self, plan: TradePlan, client_order_id: str) -> OrderResult:
        # منع التكرار: نفس المفتاح يُرجع نفس النتيجة دون إنشاء أمر جديد
        if client_order_id in self._orders:
            return self._orders[client_order_id]

        cost = plan.quantity * plan.entry
        self._cash -= cost
        self._open_positions += 1
        result = OrderResult(
            order_id=client_order_id,
            status="FILLED",
            detail=f"paper fill: {plan.side.value} {plan.quantity} @ {plan.entry}",
        )
        self._orders[client_order_id] = result
        return result
