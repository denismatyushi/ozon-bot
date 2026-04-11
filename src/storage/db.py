import logging
import os
from datetime import datetime, timedelta

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT,
    price INTEGER NOT NULL,
    original_price INTEGER,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_history_lookup
    ON price_history(source, product_id);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    product_id TEXT NOT NULL,
    price INTEGER NOT NULL,
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedup
    ON notifications(source, product_id, price);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    products_scanned INTEGER DEFAULT 0,
    anomalies_found INTEGER DEFAULT 0,
    notifications_sent INTEGER DEFAULT 0
);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("Database initialized at %s", self.db_path)

    async def close(self):
        if self._db:
            await self._db.close()

    async def save_prices(self, products: list[dict]):
        if not self._db or not products:
            return
        await self._db.executemany(
            """INSERT INTO price_history (source, product_id, product_name, price, original_price, fetched_at)
               VALUES (:source, :product_id, :name, :sale_price, :original_price, :fetched_at)""",
            products,
        )
        await self._db.commit()

    async def get_price_history(self) -> dict[str, list[int]]:
        """Get price history grouped by source:product_id."""
        if not self._db:
            return {}
        cursor = await self._db.execute(
            "SELECT source, product_id, price FROM price_history ORDER BY fetched_at"
        )
        rows = await cursor.fetchall()
        history: dict[str, list[int]] = {}
        for source, product_id, price in rows:
            key = f"{source}:{product_id}"
            history.setdefault(key, []).append(price)
        return history

    async def was_notified(self, source: str, product_id: str, price: int) -> bool:
        """Check if we already sent a notification for this product at this price."""
        if not self._db:
            return False
        cutoff = datetime.now() - timedelta(hours=24)
        cursor = await self._db.execute(
            """SELECT 1 FROM notifications
               WHERE source = ? AND product_id = ? AND price = ? AND notified_at > ?""",
            (source, product_id, price, cutoff),
        )
        row = await cursor.fetchone()
        return row is not None

    async def mark_notified(self, source: str, product_id: str, price: int):
        if not self._db:
            return
        await self._db.execute(
            """INSERT OR REPLACE INTO notifications (source, product_id, price, notified_at)
               VALUES (?, ?, ?, ?)""",
            (source, product_id, price, datetime.now()),
        )
        await self._db.commit()

    async def save_scan_run(
        self,
        started_at: datetime,
        finished_at: datetime,
        products_scanned: int,
        anomalies_found: int,
        notifications_sent: int,
    ):
        if not self._db:
            return
        await self._db.execute(
            """INSERT INTO scan_runs (started_at, finished_at, products_scanned, anomalies_found, notifications_sent)
               VALUES (?, ?, ?, ?, ?)""",
            (started_at, finished_at, products_scanned, anomalies_found, notifications_sent),
        )
        await self._db.commit()
