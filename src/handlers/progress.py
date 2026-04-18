"""Student dashboard: level, XP, streak, vocab & grammar stats."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from src.content.grammar import lessons_for_level
from src.content.levels import LEVELS
from src.content.vocabulary import words_for_level
from src.keyboards.common import back_to_menu
from src.services.gamification import next_rank, rank_for
from src.storage.db import Database

router = Router(name="progress")


async def _render(tg_id: int, db: Database) -> str:
    user = await db.get_user(tg_id) or {}
    level = user.get("level") or "—"
    level_name = LEVELS[level].name if level in LEVELS else "не выбран"

    totals = await db.totals(tg_id)
    today = await db.today_stats(tg_id)
    vocab = await db.vocab_counts(tg_id)
    grammar_done = await db.grammar_progress(tg_id)

    total_xp = totals.get("total_xp", 0) or 0
    streak = totals.get("current_streak", 0) or 0
    best_streak = totals.get("longest_streak", 0) or 0

    rank = rank_for(total_xp)
    nxt = next_rank(total_xp)
    next_line = (
        f"\nДо следующего ранга «{nxt[0]}»: <b>{nxt[1]} XP</b>" if nxt else
        "\n🎖 Максимальный ранг достигнут!"
    )

    vocab_total = len(words_for_level(level)) if level in LEVELS else 0
    grammar_total = len(lessons_for_level(level)) if level in LEVELS else 0
    grammar_completed = len([1 for l in lessons_for_level(level) if grammar_done.get(l.id, {}).get("best_score", 0) >= 75])

    acc = 0
    seen = vocab.get("total_seen") or 0
    if seen:
        acc = round((vocab.get("total_correct") or 0) * 100 / seen)

    return (
        f"📊 <b>Ваш прогресс</b>\n\n"
        f"Уровень: <b>{level}</b> · {level_name}\n"
        f"Ранг: {rank}\n"
        f"Всего XP: <b>{total_xp}</b>{next_line}\n"
        f"🔥 Streak: {streak} дн. (рекорд {best_streak})\n\n"
        f"<b>Сегодня:</b> {today.get('xp', 0)} XP · "
        f"{today.get('correct', 0)}/{today.get('answers', 0)} ответов\n\n"
        f"<b>Словарь ({level}):</b> {vocab.get('studied') or 0}/{vocab_total} карточек · "
        f"🏆 выучено: {vocab.get('learned') or 0} · точность {acc}%\n"
        f"<b>Грамматика ({level}):</b> {grammar_completed}/{grammar_total} тем пройдено"
    )


@router.message(Command("progress"))
async def cmd_progress(message: Message, db: Database):
    text = await _render(message.from_user.id, db)
    await message.answer(text, reply_markup=back_to_menu())


@router.callback_query(F.data == "progress")
async def cb_progress(cb: CallbackQuery, db: Database):
    text = await _render(cb.from_user.id, db)
    await cb.message.edit_text(text, reply_markup=back_to_menu())
    await cb.answer()
