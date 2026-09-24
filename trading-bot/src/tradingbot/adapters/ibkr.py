"""
محوّل Interactive Brokers عبر ib_insync — ربط فعلي جاهز.

كل شيء موصول ومكتوب؛ ينقصه فقط بيانات اتصالك (host/port/clientId) في .env
وتشغيل TWS أو IB Gateway. لا حاجة لتعديل الكود عند إضافة بياناتك.

نقاط أمان مضمّنة:
- كل أمر يحمل orderRef = client_order_id (Idempotency) لمنع التكرار.
- أمر مركّب (bracketOrder): دخول + جني ربح + وقف خسارة ذرّياً — لا صفقة
  بدون وقف خسارة أبداً.
- ابدأ على المنفذ 7497 (Paper) قبل 7496 (Live).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from ..domain.models import AccountState, Side, TradePlan
from .base import BrokerAdapter, OrderResult

logger = logging.getLogger("tradingbot.ibkr")


class IBKRAdapter(BrokerAdapter):
    supports_execution = True

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,          # 7497 = Paper، 7496 = Live
        client_id: int = 1,
        account: str = "",         # رقم الحساب (اختياري؛ يُلتقط تلقائياً)
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.account = account
        self._ib = None
        self._placed: dict[str, OrderResult] = {}  # تتبّع Idempotency محلي

    @property
    def name(self) -> str:
        return "ibkr"

    # ------------------------------------------------------------------ #
    def connect(self) -> None:
        """يفتح اتصالاً بـ TWS/Gateway. يتطلب تشغيلهما وبياناتك في .env."""
        try:
            from ib_insync import IB
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ثبّت ib_insync لتفعيل التنفيذ: pip install ib_insync"
            ) from exc

        self._ib = IB()
        self._ib.connect(self.host, self.port, clientId=self.client_id)
        logger.info("متصل بـ IBKR على %s:%s (clientId=%s)",
                    self.host, self.port, self.client_id)

    def disconnect(self) -> None:
        if self._ib is not None and self._ib.isConnected():
            self._ib.disconnect()

    def _require_connection(self):
        if self._ib is None or not self._ib.isConnected():
            raise RuntimeError("غير متصل بـ IBKR — استدعِ connect() أولاً")
        return self._ib

    # ------------------------------------------------------------------ #
    def get_account_state(self) -> AccountState:
        """يجلب حالة الحساب الحقيقية (مصدر الحقيقة للمخاطر)."""
        ib = self._require_connection()
        summary = ib.accountSummary(self.account) if self.account else ib.accountSummary()

        values = {row.tag: row.value for row in summary}
        equity = Decimal(values.get("NetLiquidation", "0") or "0")
        cash = Decimal(values.get("AvailableFunds", values.get("TotalCashValue", "0")) or "0")

        positions = [p for p in ib.positions() if p.position != 0]
        return AccountState(
            equity=equity,
            cash_available=cash,
            open_positions=len(positions),
        )

    def _build_contract(self, symbol: str):
        """يبني ويُصادق على عقد السهم (يوسَّع للخيارات لاحقاً)."""
        from ib_insync import Stock

        ib = self._require_connection()
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        return contract

    def place_bracket_order(self, plan: TradePlan, client_order_id: str) -> OrderResult:
        """
        يرسل أمراً مركّباً (دخول + هدف + وقف) عبر IBKR.
        client_order_id يمنع التكرار عند إعادة المحاولة.
        """
        # منع التكرار محلياً قبل أي إرسال
        if client_order_id in self._placed:
            return self._placed[client_order_id]

        ib = self._require_connection()
        contract = self._build_contract(plan.symbol)

        action = "BUY" if plan.side == Side.BUY else "SELL"
        qty = float(plan.quantity)

        # أمر مركّب: limit للدخول + takeProfit + stopLoss (ذرّي)
        bracket = ib.bracketOrder(
            action=action,
            quantity=qty,
            limitPrice=float(plan.entry),
            takeProfitPrice=float(plan.take_profit),
            stopLossPrice=float(plan.stop_loss),
        )

        trades = []
        for order in bracket:
            order.orderRef = client_order_id  # ختم التفرّد على كل جزء
            trades.append(ib.placeOrder(contract, order))

        parent = trades[0]
        result = OrderResult(
            order_id=str(parent.order.orderId),
            status=parent.orderStatus.status or "Submitted",
            detail=f"IBKR bracket: {action} {qty} {plan.symbol} @ {plan.entry}",
        )
        self._placed[client_order_id] = result
        logger.info("أُرسل أمر IBKR: %s", result.detail)
        return result
