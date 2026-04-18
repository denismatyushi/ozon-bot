"""The «Урок дня» — a curated mini-course that mixes vocab SRS, grammar theory
and a short quiz. Currently it bootstraps into vocab training; we reuse the
vocab handler's state machine.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.content.grammar import lessons_for_level
from src.content.vocabulary import words_for_level
from src.keyboards.common import main_menu
from src.storage.db import Database

router = Router(name="lesson")


@router.callback_query(F.data == "lesson:start")
async def cb_lesson_start(cb: CallbackQuery, state: FSMContext, db: Database):
    user = await db.get_user(cb.from_user.id)
    level = (user or {}).get("level")
    if not level:
        await cb.answer("Сначала выберите уровень", show_alert=True)
        return

    vocab_total = len(words_for_level(level))
    studied = len(await db.known_word_ids(cb.from_user.id))
    grammar_done = await db.grammar_progress(cb.from_user.id)
    grammar_remaining = [
        l for l in lessons_for_level(level)
        if grammar_done.get(l.id, {}).get("best_score", 0) < 75
    ]
    suggested_grammar = grammar_remaining[0] if grammar_remaining else None

    text = (
        f"📚 <b>Урок дня · {level}</b>\n\n"
        f"План на сегодня:\n"
        f"1️⃣ Словарь — 10 карточек (SRS + новые слова)\n"
        f"2️⃣ Грамматика — тема "
        + (f"«{suggested_grammar.title}»" if suggested_grammar else "— все темы уровня пройдены! 🏆")
        + "\n\n"
        f"📊 Словарь уровня: {studied}/{vocab_total} слов изучено.\n\n"
        f"Начнём со словаря — это разогреет память."
    )

    rows = [[InlineKeyboardButton(text="▶️ Начать со словаря", callback_data="vocab:start")]]
    if suggested_grammar:
        rows.append([InlineKeyboardButton(
            text=f"📖 Перейти к грамматике: {suggested_grammar.title}",
            callback_data=f"grammar:open:{suggested_grammar.id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()
