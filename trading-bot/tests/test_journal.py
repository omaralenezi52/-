"""اختبار دفتر الصفقات على SQLite (ملف مؤقت)."""
from decimal import Decimal

from tradingbot.domain.models import (
    Decision,
    MarketRegime,
    Recommendation,
    Side,
    TradePlan,
)
from tradingbot.journal.trade_journal import TradeJournal


def make_rec():
    plan = TradePlan(symbol="AAPL", side=Side.BUY, entry=Decimal("100"),
                     stop_loss=Decimal("98"), take_profit=Decimal("106"),
                     quantity=Decimal("10"), risk_amount=Decimal("20"),
                     risk_reward_ratio=Decimal("3"))
    return Recommendation(symbol="AAPL", decision=Decision.BUY, confidence=0.78,
                          regime=MarketRegime.TRENDING_UP, plan=plan,
                          rationale="توافق قوي")


def test_journal_logs_recommendation(tmp_path):
    j = TradeJournal(sqlite_path=tmp_path / "j.db")
    j.log_recommendation(make_rec())
    assert j.stats()["total_recommendations"] == 1


def test_journal_trade_lifecycle(tmp_path):
    j = TradeJournal(sqlite_path=tmp_path / "j.db")
    rec = make_rec()
    j.log_trade(rec, "oid-1")
    s = j.stats()
    assert s["open_trades"] == 1 and s["closed_trades"] == 0

    j.close_trade("oid-1", exit_price=106.0, pnl=60.0)
    s = j.stats()
    assert s["open_trades"] == 0
    assert s["closed_trades"] == 1
    assert s["win_rate"] == 1.0
    assert s["total_pnl"] == 60.0


def test_journal_idempotent_trade(tmp_path):
    j = TradeJournal(sqlite_path=tmp_path / "j.db")
    rec = make_rec()
    j.log_trade(rec, "oid-dup")
    j.log_trade(rec, "oid-dup")   # نفس المفتاح ⇒ لا يتكرر
    assert j.stats()["open_trades"] == 1


def test_journal_persists_across_instances(tmp_path):
    db = tmp_path / "j.db"
    TradeJournal(sqlite_path=db).log_recommendation(make_rec())
    # نسخة جديدة تقرأ نفس الملف ⇒ البيانات باقية
    assert TradeJournal(sqlite_path=db).stats()["total_recommendations"] == 1


def test_recent_trades(tmp_path):
    j = TradeJournal(sqlite_path=tmp_path / "j.db")
    j.log_trade(make_rec(), "oid-A")
    recent = j.recent_trades()
    assert recent[0]["symbol"] == "AAPL" and recent[0]["status"] == "OPEN"
