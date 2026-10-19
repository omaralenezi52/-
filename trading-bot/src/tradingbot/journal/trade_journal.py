"""
دفتر الصفقات (Trade Journal) — ذاكرة البوت الدائمة.

يدعم محرّكين:
- PostgreSQL (للإنتاج): دائم، يبقى بعد إعادة النشر. يُفعّل عبر DATABASE_URL.
- SQLite (محلي/اختبار): ملف بسيط، افتراضي عند غياب DATABASE_URL.

⚠️ على الاستضافة (حاويات Docker) استخدم Postgres — ملف SQLite يُمسح عند
كل Redeploy لأن نظام ملفات الحاوية مؤقت.

يسجّل كل توصية وكل صفقة، ويوفّر استعلامات الأداء وأساس التعلّم.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("tradingbot.journal")

DEFAULT_SQLITE = Path("data") / "journal.db"


class TradeJournal:
    def __init__(self, database_url: str = "", sqlite_path=DEFAULT_SQLITE) -> None:
        # Postgres إذا وُجد DATABASE_URL يبدأ بـ postgres، وإلا SQLite
        self.is_postgres = database_url.startswith(("postgres://", "postgresql://"))
        self.database_url = database_url
        self.sqlite_path = Path(sqlite_path)
        # علامة المعامل تختلف بين المحرّكين
        self._ph = "%s" if self.is_postgres else "?"
        if not self.is_postgres:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------- الاتصال ------------------------- #
    def _conn(self):
        if self.is_postgres:
            import psycopg  # استيراد كسول
            return psycopg.connect(self.database_url)
        import sqlite3
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _autoinc(self) -> str:
        return "SERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

    def _init_schema(self) -> None:
        pk = self._autoinc()
        with self._conn() as c:
            cur = c.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id {pk},
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    confidence REAL,
                    regime TEXT,
                    entry REAL, stop_loss REAL, take_profit REAL,
                    quantity REAL,
                    rationale TEXT
                )
            """)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS trades (
                    id {pk},
                    client_order_id TEXT UNIQUE,
                    opened_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry REAL NOT NULL,
                    stop_loss REAL, take_profit REAL,
                    quantity REAL NOT NULL,
                    status TEXT DEFAULT 'OPEN',
                    exit_price REAL,
                    pnl REAL,
                    closed_at TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_symbol ON recommendations(symbol)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_trade_status ON trades(status)")
            c.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _q(self, sql: str) -> str:
        """يستبدل علامة المعامل ? بـ %s في وضع Postgres."""
        return sql.replace("?", self._ph) if self.is_postgres else sql

    # ------------------------- تسجيل ------------------------- #
    def log_recommendation(self, rec) -> None:
        plan = rec.plan
        with self._conn() as c:
            c.cursor().execute(self._q(
                """INSERT INTO recommendations
                   (created_at, symbol, decision, confidence, regime,
                    entry, stop_loss, take_profit, quantity, rationale)
                   VALUES (?,?,?,?,?,?,?,?,?,?)"""),
                (self._now(), rec.symbol, rec.decision.value, rec.confidence,
                 rec.regime.value,
                 float(plan.entry) if plan else None,
                 float(plan.stop_loss) if plan else None,
                 float(plan.take_profit) if plan else None,
                 float(plan.quantity) if plan else None,
                 rec.rationale),
            )
            c.commit()

    def log_trade(self, rec, client_order_id: str) -> None:
        plan = rec.plan
        if plan is None:
            return
        try:
            with self._conn() as c:
                c.cursor().execute(self._q(
                    """INSERT INTO trades
                       (client_order_id, opened_at, symbol, side, entry,
                        stop_loss, take_profit, quantity, status)
                       VALUES (?,?,?,?,?,?,?,?, 'OPEN')"""),
                    (client_order_id, self._now(), rec.symbol, plan.side.value,
                     float(plan.entry), float(plan.stop_loss),
                     float(plan.take_profit), float(plan.quantity)),
                )
                c.commit()
        except Exception:
            logger.info("صفقة مكرّرة أو خطأ إدراج — تجاهل")

    def close_trade(self, client_order_id: str, exit_price: float, pnl: float) -> None:
        with self._conn() as c:
            c.cursor().execute(self._q(
                """UPDATE trades SET status='CLOSED', exit_price=?, pnl=?, closed_at=?
                   WHERE client_order_id=?"""),
                (exit_price, pnl, self._now(), client_order_id),
            )
            c.commit()

    # ------------------------- استعلامات ------------------------- #
    def _fetchall(self, sql: str, params=()) -> list[tuple]:
        with self._conn() as c:
            cur = c.cursor()
            cur.execute(self._q(sql), params)
            return cur.fetchall()

    def stats(self) -> dict:
        pnls = [r[0] for r in self._fetchall(
            "SELECT pnl FROM trades WHERE status='CLOSED' AND pnl IS NOT NULL")]
        total_recs = self._fetchall("SELECT COUNT(*) FROM recommendations")[0][0]
        open_trades = self._fetchall("SELECT COUNT(*) FROM trades WHERE status='OPEN'")[0][0]
        wins = [p for p in pnls if p > 0]
        closed = len(pnls)
        return {
            "total_recommendations": total_recs,
            "open_trades": open_trades,
            "closed_trades": closed,
            "wins": len(wins),
            "win_rate": (len(wins) / closed) if closed else 0.0,
            "total_pnl": round(sum(pnls), 2),
        }

    def recent_trades(self, limit: int = 5) -> list[dict]:
        rows = self._fetchall(
            "SELECT symbol, side, entry, pnl, status FROM trades ORDER BY id DESC LIMIT ?",
            (limit,))
        return [
            {"symbol": r[0], "side": r[1], "entry": r[2], "pnl": r[3], "status": r[4]}
            for r in rows
        ]
