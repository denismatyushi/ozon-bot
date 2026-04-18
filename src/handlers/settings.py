"""User preferences: daily goal, reminders, level reset."""
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.content.levels import LEVELS
from src.keyboards.common import main_menu
from src.storage.db import Database

router = Router(name="settings")


GOAL_OPTIONS = (5, 10, 15, 30, 60)


def _render_kb(daily_goal: int, reminders_on: bool) -> InlineKeyboardMarkup:
    goal_row = [
        InlineKeyboardButton(
            text=("✅ " if g == daily_goal else "") + f"{g} мин",
            callback_data=f"settings:goal:{g}",
        )
        for g in GOAL_OPTIONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=[
        goal_row,
        [InlineKeyboardButton(
            text=("🔔 Напоминания: ВКЛ" if reminders_on else "🔕 Напоминания: ВЫКЛ"),
            callback_data="settings:reminders:toggle",
        )],
        [InlineKeyboardButton(text="🎯 Сменить уровень", callback_data="placement:start")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


async def _render(tg_id: int, db: Database) -> tuple[str, InlineKeyboardMarkup]:
    user = await db.get_user(tg_id) or {}
    level = user.get("level") or "—"
    level_name = LEVELS.get(level).name if level in LEVELS else "не выбран"
    daily_goal = user.get("daily_goal") or 15
    reminders_on = bool(user.get("reminders_on"))
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"Уровень: <b>{level}</b> · {level_name}\n"
        f"Цель на день: <b>{daily_goal} мин</b>\n"
        f"Напоминания: <b>{'включены' if reminders_on else 'выключены'}</b>\n\n"
        "Выберите параметр ниже:"
    )
    return text, _render_kb(daily_goal, reminders_on)


@router.callback_query(F.data == "settings")
async def cb_settings(cb: CallbackQuery, db: Database):
    text, kb = await _render(cb.from_user.id, db)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("settings:goal:"))
async def cb_goal(cb: CallbackQuery, db: Database):
    minutes = int(cb.data.split(":")[-1])
    await db.set_daily_goal(cb.from_user.id, minutes)
    text, kb = await _render(cb.from_user.id, db)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer(f"Цель: {minutes} мин/день")


@router.callback_query(F.data == "settings:reminders:toggle")
async def cb_reminders(cb: CallbackQuery, db: Database):
    user = await db.get_user(cb.from_user.id) or {}
    on = not bool(user.get("reminders_on"))
    await db.set_reminders(cb.from_user.id, on)
    text, kb = await _render(cb.from_user.id, db)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer("Напоминания: " + ("ВКЛ" if on else "ВЫКЛ"))
