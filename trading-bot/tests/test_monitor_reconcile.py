"""اختبارات المراقبة والمطابقة."""
from decimal import Decimal

from tradingbot.monitor import HealthMonitor
from tradingbot.reconcile import Reconciler
from tradingbot.domain.models import AccountState


class FakeNotifier:
    def __init__(self):
        self.messages = []
    def send_text(self, text):
        self.messages.append(text)
        return True


class FakeBroker:
    def __init__(self, positions):
        self._positions = positions
    @property
    def name(self):
        return "fake"
    def get_account_state(self):
        return AccountState(equity=Decimal("100000"),
                            cash_available=Decimal("100000"),
                            open_positions=self._positions)


class FakeJournal:
    def __init__(self, open_trades):
        self._open = open_trades
    def stats(self):
        return {"open_trades": self._open}


# ---------------- Monitor ---------------- #
def test_monitor_healthy_after_success():
    m = HealthMonitor()
    m.record_success()
    assert m.check() is True
    assert "سليم" in m.health_text()


def test_monitor_dead_man_triggers_alert():
    notifier = FakeNotifier()
    m = HealthMonitor(notifier=notifier, stale_after_seconds=0)
    m.record_success()  # الآن، لكن العتبة 0 ⇒ يُعتبر متجمّداً فوراً
    assert m.check() is False
    assert len(notifier.messages) == 1          # نبّه مرة
    m.check()
    assert len(notifier.messages) == 1          # لا يكرّر الإزعاج


def test_monitor_no_data_yet_is_not_stale():
    m = HealthMonitor(stale_after_seconds=0)
    assert m.check() is True  # لم تبدأ بعد


# ---------------- Reconcile ---------------- #
def test_reconcile_matched_no_alert():
    notifier = FakeNotifier()
    r = Reconciler(FakeBroker(positions=2), FakeJournal(open_trades=2), notifier)
    report = r.reconcile()
    assert report["discrepancies"] == []
    assert notifier.messages == []


def test_reconcile_detects_discrepancy():
    notifier = FakeNotifier()
    r = Reconciler(FakeBroker(positions=1), FakeJournal(open_trades=3), notifier)
    report = r.reconcile()
    assert report["discrepancies"]
    assert any("تضارب" in m for m in notifier.messages)
