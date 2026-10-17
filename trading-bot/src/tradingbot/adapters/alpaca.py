"""
محوّل Alpaca عبر alpaca-py — ربط فعلي جاهز (تنفيذ سحابي، بلا برنامج وسيط).

ميزة Alpaca: سحابي بالكامل (لا يحتاج TWS/Gateway مثل IBKR)، وREST نظيف.
يقرأ المفاتيح من البيئة وقت التشغيل — لا تُكتب في الكود أبداً.

نقاط أمان مضمّنة:
- client_order_id (Idempotency) لمنع تكرار الأمر.
- أمر مركّب (bracket): دخول + جني ربح + وقف خسارة ذرّياً.
- ابدأ دائماً على Paper (paper=True) قبل الحساب الحقيقي.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from ..domain.models import AccountState, Side, TradePlan
from .base import BrokerAdapter, OrderResult

logger = logging.getLogger("tradingbot.alpaca")


class AlpacaAdapter(BrokerAdapter):
    supports_execution = True

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        paper: bool = True,
        client=None,  # يُحقن للاختبار؛ وإلا يُبنى كسولاً من alpaca-py
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self._client = client

    @property
    def name(self) -> str:
        return "alpaca"

    def _get_client(self):
        if self._client is None:
            try:
                from alpaca.trading.client import TradingClient
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "ثبّت alpaca-py لتفعيل Alpaca: pip install alpaca-py"
                ) from exc
            if not self.api_key or not self.secret_key:
                raise RuntimeError("مفاتيح Alpaca مفقودة — عيّنها في .env")
            self._client = TradingClient(self.api_key, self.secret_key, paper=self.paper)
        return self._client

    def get_account_state(self) -> AccountState:
        """يجلب حالة الحساب الحقيقية (مصدر الحقيقة للمخاطر)."""
        client = self._get_client()
        account = client.get_account()
        positions = client.get_all_positions()
        return AccountState(
            equity=Decimal(str(account.equity)),
            cash_available=Decimal(str(account.cash)),
            open_positions=len(positions),
        )

    def place_bracket_order(self, plan: TradePlan, client_order_id: str) -> OrderResult:
        """يرسل أمراً مركّباً (دخول limit + هدف + وقف) عبر Alpaca."""
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            StopLossRequest,
            TakeProfitRequest,
        )

        client = self._get_client()
        side = OrderSide.BUY if plan.side == Side.BUY else OrderSide.SELL

        req = LimitOrderRequest(
            symbol=plan.symbol,
            qty=float(plan.quantity),
            side=side,
            time_in_force=TimeInForce.GTC,
            limit_price=float(plan.entry),
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=float(plan.take_profit)),
            stop_loss=StopLossRequest(stop_price=float(plan.stop_loss)),
            client_order_id=client_order_id,  # يمنع التكرار
        )
        order = client.submit_order(req)
        result = OrderResult(
            order_id=str(order.id),
            status=str(getattr(order, "status", "accepted")),
            detail=f"Alpaca bracket: {plan.side.value} {plan.quantity} {plan.symbol} @ {plan.entry}",
        )
        logger.info("أُرسل أمر Alpaca: %s", result.detail)
        return result
