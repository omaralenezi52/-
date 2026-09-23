"""اختبارات أمان مستقبِل الـ Webhook."""
from tradingbot.config import Settings
from tradingbot.domain.models import TradeMode
from tradingbot.webhook.app import create_app

from fastapi.testclient import TestClient


def make_client(captured=None):
    settings = Settings(webhook_secret="supersecret123", mode=TradeMode.ADVISOR)
    def on_signal(sig):
        if captured is not None:
            captured.append(sig)
    return TestClient(create_app(settings, on_signal=on_signal))


def test_health():
    c = make_client()
    assert c.get("/health").json()["status"] == "ok"


def test_rejects_wrong_secret():
    c = make_client()
    r = c.post("/webhook/tradingview", json={
        "secret": "wrongsecret", "symbol": "AAPL", "action": "BUY", "price": 100,
    })
    assert r.status_code == 401


def test_accepts_valid_signal():
    captured = []
    c = make_client(captured)
    r = c.post("/webhook/tradingview", json={
        "secret": "supersecret123", "symbol": "aapl",
        "action": "buy", "price": 178.5,
    })
    assert r.status_code == 200
    assert r.json()["action"] == "BUY"
    assert captured[0].symbol == "AAPL"   # طُبِّع لحروف كبيرة


def test_rejects_invalid_action():
    c = make_client()
    r = c.post("/webhook/tradingview", json={
        "secret": "supersecret123", "symbol": "AAPL",
        "action": "HODL", "price": 100,
    })
    assert r.status_code == 422


def test_rejects_negative_price():
    c = make_client()
    r = c.post("/webhook/tradingview", json={
        "secret": "supersecret123", "symbol": "AAPL",
        "action": "BUY", "price": -5,
    })
    assert r.status_code == 422
