"""Grammar module: list lessons by level, read theory, solve exercises."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.content.grammar import BY_LEVEL, get_lesson, lessons_for_level
from src.content.levels import LEVEL_ORDER
from src.keyboards.common import answer_options, main_menu
from src.services.gamification import XP_GRAMMAR_EXERCISE_CORRECT, XP_LESSON_COMPLETED_BONUS
from src.storage.db import Database
from src.utils.format import md_to_html

router = Router(name="grammar")


class GrammarStates(StatesGroup):
    exercising = State()


def _lessons_keyboard(level: str, done: dict[str, dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for lesson in lessons_for_level(level):
        mark = ""
        info = done.get(lesson.id)
        if info:
            mark = f" · 🏆 {info['best_score']}%"
        rows.append([InlineKeyboardButton(
            text=f"• {lesson.title}{mark}",
            callback_data=f"grammar:open:{lesson.id}",
        )])

    # switch level buttons
    level_row = [
        InlineKeyboardButton(
            text=("✅ " if code == level else "") + code,
            callback_data=f"grammar:level:{code}",
        )
        for code in LEVEL_ORDER
    ]
    rows.append(level_row)
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "grammar:list")
async def cb_list(cb: CallbackQuery, db: Database):
    user = await db.get_user(cb.from_user.id)
    level = (user or {}).get("level") or "A1"
    done = await db.grammar_progress(cb.from_user.id)
    text = (
        f"📖 <b>Грамматика · уровень {level}</b>\n\n"
        f"Выберите тему. Рядом с изученными — ваш лучший результат."
    )
    await cb.message.edit_text(text, reply_markup=_lessons_keyboard(level, done))
    await cb.answer()


@router.callback_query(F.data.startswith("grammar:level:"))
async def cb_level_filter(cb: CallbackQuery, db: Database):
    level = cb.data.split(":")[-1]
    if level not in BY_LEVEL:
        await cb.answer("Неизвестный уровень", show_alert=True)
        return
    done = await db.grammar_progress(cb.from_user.id)
    text = f"📖 <b>Грамматика · уровень {level}</b>"
    await cb.message.edit_text(text, reply_markup=_lessons_keyboard(level, done))
    await cb.answer()


@router.callback_query(F.data.startswith("grammar:open:"))
async def cb_open(cb: CallbackQuery):
    lesson_id = cb.data.split("grammar:open:")[-1]
    lesson = get_lesson(lesson_id)
    if not lesson:
        await cb.answer("Урок не найден", show_alert=True)
        return

    text = (
        f"📖 <b>{lesson.title}</b>  <i>· {lesson.level}</i>\n\n"
        f"{md_to_html(lesson.theory)}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 К упражнениям", callback_data=f"grammar:start:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ К списку тем", callback_data="grammar:list")],
    ])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("grammar:start:"))
async def cb_start(cb: CallbackQuery, state: FSMContext):
    lesson_id = cb.data.split("grammar:start:")[-1]
    lesson = get_lesson(lesson_id)
    if not lesson:
        await cb.answer("Урок не найден", show_alert=True)
        return
    await state.set_state(GrammarStates.exercising)
    await state.update_data(lesson_id=lesson_id, idx=0, correct=0)
    await _ask_exercise(cb, state)
    await cb.answer()


async def _ask_exercise(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    lesson = get_lesson(data["lesson_id"])
    idx = data["idx"]
    ex = lesson.exercises[idx]
    text = (
        f"🎯 <b>{lesson.title}</b>\n"
        f"Упражнение {idx + 1} из {len(lesson.exercises)}\n\n"
        f"{ex.prompt}"
    )
    await cb.message.edit_text(text, reply_markup=answer_options(list(ex.options), prefix="grammar:ans"))


@router.callback_query(GrammarStates.exercising, F.data.startswith("grammar:ans:"))
async def cb_answer(cb: CallbackQuery, state: FSMContext, db: Database):
    choice = int(cb.data.split(":")[-1])
    data = await state.get_data()
    lesson = get_lesson(data["lesson_id"])
    idx: int = data["idx"]
    ex = lesson.exercises[idx]
    is_correct = choice == ex.correct

    data["correct"] = data.get("correct", 0) + (1 if is_correct else 0)
    data["idx"] = idx + 1
    await state.update_data(**data)
    await db.add_activity(
        cb.from_user.id,
        xp=XP_GRAMMAR_EXERCISE_CORRECT if is_correct else 0,
        answers=1,
        correct=1 if is_correct else 0,
    )

    feedback = (
        f"✅ <b>Верно!</b>" if is_correct
        else f"❌ <b>Правильный ответ:</b> {ex.options[ex.correct]}"
    )
    if ex.explanation:
        feedback += f"\n<i>{ex.explanation}</i>"

    last = data["idx"] >= len(lesson.exercises)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🏁 Завершить" if last else "➡️ Дальше",
            callback_data="grammar:next",
        )
    ]])
    await cb.message.edit_text(feedback, reply_markup=kb)
    await cb.answer()


@router.callback_query(GrammarStates.exercising, F.data == "grammar:next")
async def cb_next(cb: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    lesson = get_lesson(data["lesson_id"])
    if data["idx"] < len(lesson.exercises):
        await _ask_exercise(cb, state)
        await cb.answer()
        return

    # Finished
    correct = data["correct"]
    total = len(lesson.exercises)
    score = round(correct * 100 / total) if total else 0
    await db.save_grammar_attempt(cb.from_user.id, lesson.id, score)

    bonus = XP_LESSON_COMPLETED_BONUS if score >= 75 else 0
    if bonus:
        await db.add_activity(cb.from_user.id, xp=bonus, answers=0, correct=0)

    user = await db.get_user(cb.from_user.id)
    level = (user or {}).get("level")

    text = (
        f"🏆 <b>{lesson.title}</b>\n\n"
        f"Результат: <b>{correct}/{total}</b> ({score}%)\n"
        + (f"+{bonus} XP бонус за хороший результат! 💫\n" if bonus else "")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Пройти ещё раз", callback_data=f"grammar:start:{lesson.id}")],
        [InlineKeyboardButton(text="📖 К списку тем", callback_data="grammar:list")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])
    await state.clear()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()
