import logging
import os
from datetime import date, datetime

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id        INTEGER PRIMARY KEY,
    username     TEXT,
    first_name   TEXT,
    level        TEXT,                 -- A1 / A2 / B1 / B2 / C1, NULL until placement done
    daily_goal   INTEGER DEFAULT 15,   -- minutes per day
    reminders_on INTEGER DEFAULT 1,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vocab_progress (
    tg_id          INTEGER NOT NULL,
    word_id        TEXT    NOT NULL,       -- stable id like "A1:hello"
    box            INTEGER NOT NULL DEFAULT 1,   -- Leitner 1..5
    correct_streak INTEGER NOT NULL DEFAULT 0,
    total_seen     INTEGER NOT NULL DEFAULT 0,
    total_correct  INTEGER NOT NULL DEFAULT 0,
    next_review_at TIMESTAMP,
    last_seen_at   TIMESTAMP,
    PRIMARY KEY (tg_id, word_id)
);

CREATE INDEX IF NOT EXISTS idx_vocab_due
    ON vocab_progress(tg_id, next_review_at);

CREATE TABLE IF NOT EXISTS grammar_progress (
    tg_id        INTEGER NOT NULL,
    lesson_id    TEXT    NOT NULL,          -- "A1:present-simple"
    best_score   INTEGER NOT NULL DEFAULT 0, -- 0..100
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_done_at TIMESTAMP,
    PRIMARY KEY (tg_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS daily_stats (
    tg_id     INTEGER NOT NULL,
    day       DATE    NOT NULL,
    xp        INTEGER NOT NULL DEFAULT 0,
    answers   INTEGER NOT NULL DEFAULT 0,
    correct   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tg_id, day)
);

CREATE TABLE IF NOT EXISTS placement_results (
    tg_id        INTEGER PRIMARY KEY,
    level        TEXT    NOT NULL,
    score        INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_totals (
    tg_id            INTEGER PRIMARY KEY,
    total_xp         INTEGER NOT NULL DEFAULT 0,
    current_streak   INTEGER NOT NULL DEFAULT 0,
    longest_streak   INTEGER NOT NULL DEFAULT 0,
    last_active_day  DATE
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("Database ready at %s", self.path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._db is not None, "Database.init() must be called first"
        return self._db

    # ---------- users ----------

    async def upsert_user(self, tg_id: int, username: str | None, first_name: str | None) -> None:
        await self.conn.execute(
            """INSERT INTO users (tg_id, username, first_name)
               VALUES (?, ?, ?)
               ON CONFLICT(tg_id) DO UPDATE SET
                   username   = excluded.username,
                   first_name = excluded.first_name""",
            (tg_id, username, first_name),
        )
        await self.conn.execute(
            "INSERT OR IGNORE INTO user_totals (tg_id) VALUES (?)",
            (tg_id,),
        )
        await self.conn.commit()

    async def get_user(self, tg_id: int) -> dict | None:
        cur = await self.conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def set_level(self, tg_id: int, level: str) -> None:
        await self.conn.execute("UPDATE users SET level = ? WHERE tg_id = ?", (level, tg_id))
        await self.conn.commit()

    async def set_daily_goal(self, tg_id: int, minutes: int) -> None:
        await self.conn.execute("UPDATE users SET daily_goal = ? WHERE tg_id = ?", (minutes, tg_id))
        await self.conn.commit()

    async def set_reminders(self, tg_id: int, on: bool) -> None:
        await self.conn.execute(
            "UPDATE users SET reminders_on = ? WHERE tg_id = ?", (1 if on else 0, tg_id)
        )
        await self.conn.commit()

    async def all_users_with_reminders(self) -> list[dict]:
        cur = await self.conn.execute(
            "SELECT tg_id, first_name, level FROM users WHERE reminders_on = 1 AND level IS NOT NULL"
        )
        return [dict(r) for r in await cur.fetchall()]

    # ---------- vocabulary SRS ----------

    async def get_vocab_progress(self, tg_id: int, word_id: str) -> dict | None:
        cur = await self.conn.execute(
            "SELECT * FROM vocab_progress WHERE tg_id = ? AND word_id = ?",
            (tg_id, word_id),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def upsert_vocab_progress(
        self,
        tg_id: int,
        word_id: str,
        box: int,
        correct_streak: int,
        total_seen_delta: int,
        total_correct_delta: int,
        next_review_at: datetime,
    ) -> None:
        await self.conn.execute(
            """INSERT INTO vocab_progress
                 (tg_id, word_id, box, correct_streak, total_seen, total_correct,
                  next_review_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(tg_id, word_id) DO UPDATE SET
                 box            = excluded.box,
                 correct_streak = excluded.correct_streak,
                 total_seen     = vocab_progress.total_seen + ?,
                 total_correct  = vocab_progress.total_correct + ?,
                 next_review_at = excluded.next_review_at,
                 last_seen_at   = CURRENT_TIMESTAMP""",
            (
                tg_id, word_id, box, correct_streak,
                total_seen_delta, total_correct_delta, next_review_at,
                total_seen_delta, total_correct_delta,
            ),
        )
        await self.conn.commit()

    async def due_vocab_ids(self, tg_id: int, level: str, limit: int = 20) -> list[str]:
        """Word ids due for review now — from the student's level or lower."""
        cur = await self.conn.execute(
            """SELECT word_id FROM vocab_progress
               WHERE tg_id = ? AND word_id LIKE ? AND next_review_at <= CURRENT_TIMESTAMP
               ORDER BY next_review_at ASC
               LIMIT ?""",
            (tg_id, f"{level}:%", limit),
        )
        return [r["word_id"] for r in await cur.fetchall()]

    async def known_word_ids(self, tg_id: int) -> set[str]:
        cur = await self.conn.execute(
            "SELECT word_id FROM vocab_progress WHERE tg_id = ?", (tg_id,)
        )
        return {r["word_id"] for r in await cur.fetchall()}

    async def vocab_counts(self, tg_id: int) -> dict:
        cur = await self.conn.execute(
            """SELECT
                   COUNT(*)                                    AS studied,
                   SUM(CASE WHEN box >= 4 THEN 1 ELSE 0 END)   AS learned,
                   SUM(total_seen)                             AS total_seen,
                   SUM(total_correct)                          AS total_correct
               FROM vocab_progress WHERE tg_id = ?""",
            (tg_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else {"studied": 0, "learned": 0, "total_seen": 0, "total_correct": 0}

    # ---------- grammar ----------

    async def save_grammar_attempt(self, tg_id: int, lesson_id: str, score: int) -> None:
        await self.conn.execute(
            """INSERT INTO grammar_progress (tg_id, lesson_id, best_score, attempts, last_done_at)
               VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
               ON CONFLICT(tg_id, lesson_id) DO UPDATE SET
                 best_score   = MAX(grammar_progress.best_score, excluded.best_score),
                 attempts     = grammar_progress.attempts + 1,
                 last_done_at = CURRENT_TIMESTAMP""",
            (tg_id, lesson_id, score),
        )
        await self.conn.commit()

    async def grammar_progress(self, tg_id: int) -> dict[str, dict]:
        cur = await self.conn.execute(
            "SELECT lesson_id, best_score, attempts FROM grammar_progress WHERE tg_id = ?",
            (tg_id,),
        )
        return {r["lesson_id"]: dict(r) for r in await cur.fetchall()}

    # ---------- placement ----------

    async def save_placement(self, tg_id: int, level: str, score: int, total: int) -> None:
        await self.conn.execute(
            """INSERT INTO placement_results (tg_id, level, score, total, completed_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(tg_id) DO UPDATE SET
                 level = excluded.level, score = excluded.score,
                 total = excluded.total, completed_at = CURRENT_TIMESTAMP""",
            (tg_id, level, score, total),
        )
        await self.conn.commit()

    # ---------- daily stats / xp / streak ----------

    async def add_activity(self, tg_id: int, xp: int, answers: int, correct: int) -> None:
        today = date.today().isoformat()
        await self.conn.execute(
            """INSERT INTO daily_stats (tg_id, day, xp, answers, correct)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tg_id, day) DO UPDATE SET
                 xp      = daily_stats.xp      + excluded.xp,
                 answers = daily_stats.answers + excluded.answers,
                 correct = daily_stats.correct + excluded.correct""",
            (tg_id, today, xp, answers, correct),
        )

        # Update totals + streak
        cur = await self.conn.execute(
            "SELECT total_xp, current_streak, longest_streak, last_active_day FROM user_totals WHERE tg_id = ?",
            (tg_id,),
        )
        row = await cur.fetchone()
        total_xp, cur_streak, longest, last_day = (
            (row["total_xp"], row["current_streak"], row["longest_streak"], row["last_active_day"])
            if row
            else (0, 0, 0, None)
        )

        today_d = date.today()
        if last_day == today_d.isoformat():
            new_streak = cur_streak
        elif last_day is None:
            new_streak = 1
        else:
            prev = date.fromisoformat(last_day)
            new_streak = cur_streak + 1 if (today_d - prev).days == 1 else 1
        longest = max(longest, new_streak)

        await self.conn.execute(
            """INSERT INTO user_totals (tg_id, total_xp, current_streak, longest_streak, last_active_day)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tg_id) DO UPDATE SET
                 total_xp        = user_totals.total_xp + ?,
                 current_streak  = ?,
                 longest_streak  = ?,
                 last_active_day = ?""",
            (tg_id, total_xp + xp, new_streak, longest, today_d.isoformat(),
             xp, new_streak, longest, today_d.isoformat()),
        )
        await self.conn.commit()

    async def totals(self, tg_id: int) -> dict:
        cur = await self.conn.execute(
            "SELECT total_xp, current_streak, longest_streak, last_active_day FROM user_totals WHERE tg_id = ?",
            (tg_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else {
            "total_xp": 0, "current_streak": 0, "longest_streak": 0, "last_active_day": None,
        }

    async def today_stats(self, tg_id: int) -> dict:
        today = date.today().isoformat()
        cur = await self.conn.execute(
            "SELECT xp, answers, correct FROM daily_stats WHERE tg_id = ? AND day = ?",
            (tg_id, today),
        )
        row = await cur.fetchone()
        return dict(row) if row else {"xp": 0, "answers": 0, "correct": 0}
