"""Vocabulary training with Leitner-style spaced repetition.

Flow:
  • pick a session of due + new words (up to 10)
  • for each word show a multiple-choice translation (EN → RU)
  • apply SRS update on every answer
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.content.vocabulary import get_word
from src.keyboards.common import answer_options, main_menu
from src.services.gamification import XP_VOCAB_CORRECT, XP_VOCAB_NEW_LEARNED
from src.services.lesson import pick_session_words
from src.services.quiz import build_translation_choices
from src.services.srs import next_state
from src.storage.db import Database

router = Router(name="vocab")


class VocabStates(StatesGroup):
    answering = State()


async def _start_session(cb: CallbackQuery, state: FSMContext, db: Database, level: str) -> None:
    words = await pick_session_words(db, cb.from_user.id, level=level, total=10, max_new=5)
    if not words:
        await cb.message.edit_text(
            "📭 Слова для повторения сейчас нет, а весь словарь уровня уже изучен.\n\n"
            "Поздравляю! Попробуйте повысить уровень или вернитесь позже — карточки откроются по графику.",
            reply_markup=main_menu(level),
        )
        return

    await state.set_state(VocabStates.answering)
    await state.update_data(
        queue=[w.id for w in words],
        idx=0,
        correct=0,
        wrong=0,
    )
    await _ask_next(cb, state, db)


async def _ask_next(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    queue: list[str] = data["queue"]
    idx: int = data["idx"]

    if idx >= len(queue):
        await _finish_session(cb, state, db)
        return

    word = get_word(queue[idx])
    if word is None:
        await state.update_data(idx=idx + 1)
        await _ask_next(cb, state, db)
        return

    options, correct_idx = build_translation_choices(word, direction="en_to_ru")
    await state.update_data(current_correct=correct_idx, current_word_id=word.id)

    text = (
        f"🔤 <b>Слово {idx + 1} из {len(queue)}</b>\n\n"
        f"<b>{word.en}</b>  <i>{word.transcription}</i>\n\n"
        f"Выберите перевод:"
    )
    await cb.message.edit_text(text, reply_markup=answer_options(options, prefix="vocab:ans"))


@router.callback_query(F.data == "vocab:start")
async def cb_start(cb: CallbackQuery, state: FSMContext, db: Database):
    user = await db.get_user(cb.from_user.id)
    level = user.get("level") if user else None
    if not level:
        await cb.answer("Сначала выберите уровень или пройдите тест", show_alert=True)
        return
    await _start_session(cb, state, db, level)
    await cb.answer()


@router.callback_query(VocabStates.answering, F.data.startswith("vocab:ans:"))
async def cb_answer(cb: CallbackQuery, state: FSMContext, db: Database):
    choice = int(cb.data.split(":")[-1])
    data = await state.get_data()
    word_id: str = data["current_word_id"]
    correct_idx: int = data["current_correct"]
    is_correct = (choice == correct_idx)

    word = get_word(word_id)
    if word is None:
        await cb.answer()
        return

    # SRS update
    prev = await db.get_vocab_progress(cb.from_user.id, word_id)
    prev_box = prev["box"] if prev else 1
    prev_streak = prev["correct_streak"] if prev else 0
    new_box, new_streak, next_at = next_state(prev_box, prev_streak, is_correct)
    await db.upsert_vocab_progress(
        tg_id=cb.from_user.id,
        word_id=word_id,
        box=new_box,
        correct_streak=new_streak,
        total_seen_delta=1,
        total_correct_delta=1 if is_correct else 0,
        next_review_at=next_at,
    )

    # XP + streak
    xp = XP_VOCAB_CORRECT if is_correct else 0
    if is_correct and prev_box < 4 <= new_box:
        xp += XP_VOCAB_NEW_LEARNED  # crossed into "learned" zone
    await db.add_activity(cb.from_user.id, xp=xp, answers=1, correct=1 if is_correct else 0)

    # Feedback card before next question
    if is_correct:
        header = "✅ <b>Верно!</b>"
    else:
        header = f"❌ <b>Правильный ответ:</b> {word.ru}"

    example = f"\n\n<i>{word.example_en}</i>\n{word.example_ru}" if word.example_en else ""
    footer = f"\n\nКарточка → box {new_box}/5"
    body = f"<b>{word.en}</b> — {word.ru}{example}{footer}"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➡️ Дальше", callback_data="vocab:next"),
        InlineKeyboardButton(text="⏹ Закончить", callback_data="vocab:stop"),
    ]])

    data["correct"] = data.get("correct", 0) + (1 if is_correct else 0)
    data["wrong"] = data.get("wrong", 0) + (0 if is_correct else 1)
    await state.update_data(**data)

    await cb.message.edit_text(f"{header}\n\n{body}", reply_markup=kb)
    await cb.answer()


@router.callback_query(VocabStates.answering, F.data == "vocab:next")
async def cb_next(cb: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    await state.update_data(idx=data["idx"] + 1)
    await _ask_next(cb, state, db)
    await cb.answer()


@router.callback_query(VocabStates.answering, F.data == "vocab:stop")
async def cb_stop(cb: CallbackQuery, state: FSMContext, db: Database):
    await _finish_session(cb, state, db)
    await cb.answer()


async def _finish_session(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    correct = data.get("correct", 0)
    wrong = data.get("wrong", 0)
    total = correct + wrong
    accuracy = round(correct * 100 / total) if total else 0
    await state.clear()

    user = await db.get_user(cb.from_user.id)
    level = user.get("level") if user else None

    text = (
        "🏁 <b>Тренировка словаря завершена</b>\n\n"
        f"Верно: {correct} / {total} ({accuracy}%)"
    )
    await cb.message.edit_text(text, reply_markup=main_menu(level))
