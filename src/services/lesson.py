"""Daily-lesson composition — picks vocab cards for a session.

Mixes review cards (due per SRS) with fresh words at the student's level.
"""
import random

from src.content.vocabulary import Word, get_word, words_for_level
from src.storage.db import Database


async def pick_session_words(
    db: Database,
    tg_id: int,
    level: str,
    total: int = 10,
    max_new: int = 5,
) -> list[Word]:
    """Return up to `total` words: due reviews first, then new cards."""
    due_ids = await db.due_vocab_ids(tg_id, level=level, limit=total)
    due_words = [get_word(i) for i in due_ids]
    due_words = [w for w in due_words if w is not None]

    remaining = total - len(due_words)
    if remaining <= 0:
        return due_words[:total]

    known = await db.known_word_ids(tg_id)
    fresh_pool = [w for w in words_for_level(level) if w.id not in known]
    random.shuffle(fresh_pool)
    fresh = fresh_pool[: min(remaining, max_new)]

    session = due_words + fresh
    random.shuffle(session)
    return session
