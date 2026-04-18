"""Placement test: 15 questions, derives CEFR level from results."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery

from src.content.levels import LEVELS
from src.content.placement import QUESTIONS, level_from_results
from src.keyboards.common import answer_options, main_menu
from src.services.gamification import XP_PLACEMENT_COMPLETED
from src.storage.db import Database

router = Router(name="placement")


class PlacementStates(StatesGroup):
    answering = State()


def _render_question(idx: int) -> tuple[str, list[str]]:
    q = QUESTIONS[idx]
    text = (
        f"🎯 <b>Тест уровня · Вопрос {idx + 1} из {len(QUESTIONS)}</b>\n\n"
        f"{q.prompt}"
    )
    return text, list(q.options)


@router.callback_query(F.data == "placement:start")
async def cb_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(PlacementStates.answering)
    await state.update_data(idx=0, answers=[])
    text, opts = _render_question(0)
    await cb.message.edit_text(text, reply_markup=answer_options(opts, prefix="placement:ans"))
    await cb.answer()


@router.callback_query(PlacementStates.answering, F.data.startswith("placement:ans:"))
async def cb_answer(cb: CallbackQuery, state: FSMContext, db: Database):
    choice = int(cb.data.split(":")[-1])
    data = await state.get_data()
    idx: int = data["idx"]
    answers: list[bool] = list(data.get("answers", []))

    q = QUESTIONS[idx]
    answers.append(choice == q.correct)

    idx += 1
    if idx < len(QUESTIONS):
        await state.update_data(idx=idx, answers=answers)
        text, opts = _render_question(idx)
        await cb.message.edit_text(text, reply_markup=answer_options(opts, prefix="placement:ans"))
        await cb.answer("✅" if answers[-1] else "❌")
        return

    # Done
    await state.clear()
    level = level_from_results(answers)
    correct = sum(1 for a in answers if a)
    total = len(answers)
    await db.set_level(cb.from_user.id, level)
    await db.save_placement(cb.from_user.id, level, correct, total)
    await db.add_activity(cb.from_user.id, xp=XP_PLACEMENT_COMPLETED, answers=total, correct=correct)

    info = LEVELS[level]
    text = (
        f"🎉 <b>Тест пройден!</b>\n\n"
        f"Правильных ответов: <b>{correct} из {total}</b>\n"
        f"Ваш уровень: <b>{level} — {info.name}</b>\n\n"
        f"{info.description}\n\n"
        f"+{XP_PLACEMENT_COMPLETED} XP 💫\n\n"
        f"Готовы начать учиться? Нажмите «📚 Урок дня» в меню."
    )
    await cb.message.edit_text(text, reply_markup=main_menu(level))
    await cb.answer("Готово!")
