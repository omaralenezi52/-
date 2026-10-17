"""اختبار محوّل Alpaca بعميل وهمي (بلا شبكة وبلا مفاتيح حقيقية)."""
from decimal import Decimal

import pytest

from tradingbot.adapters.alpaca import AlpacaAdapter
from tradingbot.domain.models import Side, TradePlan


class FakeAccount:
    equity = "100000"
    cash = "50000"


class FakeOrder:
    id = "order-123"
    status = "accepted"


class FakeTradingClient:
    """يحاكي TradingClient من alpaca-py دون شبكة."""
    def __init__(self):
        self.submitted = []

    def get_account(self):
        return FakeAccount()

    def get_all_positions(self):
        return [object(), object()]  # صفقتان مفتوحتان

    def submit_order(self, req):
        self.submitted.append(req)
        return FakeOrder()


def test_get_account_state_maps_fields():
    adapter = AlpacaAdapter(client=FakeTradingClient())
    state = adapter.get_account_state()
    assert state.equity == Decimal("100000")
    assert state.cash_available == Decimal("50000")
    assert state.open_positions == 2


def test_name_and_supports_execution():
    adapter = AlpacaAdapter(client=FakeTradingClient())
    assert adapter.name == "alpaca"
    assert adapter.supports_execution is True


def test_missing_keys_without_client_raises():
    # بلا عميل محقون وبلا مفاتيح ⇒ خطأ واضح (لا تعطّل صامت)
    adapter = AlpacaAdapter(api_key="", secret_key="")
    with pytest.raises(RuntimeError, match="Alpaca"):
        adapter.get_account_state()
