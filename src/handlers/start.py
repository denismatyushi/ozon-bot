"""Onboarding: /start, /menu, level picker and greeting."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.content.levels import LEVELS
from src.keyboards.common import back_to_menu, level_picker, main_menu
from src.storage.db import Database

router = Router(name="start")


WELCOME_NEW = (
    "👋 <b>Добро пожаловать в English School Bot!</b>\n\n"
    "Я ваш персональный преподаватель английского. Здесь как в настоящей школе:\n"
    "• 🎯 <b>Определим уровень</b> по тесту CEFR (A1–C1)\n"
    "• 📚 <b>Ежедневные уроки</b> под ваш уровень\n"
    "• 🔤 <b>Словарь</b> с интервальным повторением (Leitner)\n"
    "• 📖 <b>Грамматика</b> с объяснением и упражнениями\n"
    "• 📊 <b>Прогресс</b>, XP и streak — как в Duolingo\n\n"
    "Начнём со входного тестирования — это займёт 3–5 минут."
)

WELCOME_BACK = (
    "С возвращением, {name}! 👋\n"
    "Ваш уровень: <b>{level}</b> — {level_name}\n\n"
    "Готовы продолжить?"
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db: Database):
    await state.clear()
    u = message.from_user
    await db.upsert_user(u.id, u.username, u.first_name)

    user = await db.get_user(u.id)
    level = user.get("level") if user else None

    if level:
        level_name = LEVELS[level].name
        await message.answer(
            WELCOME_BACK.format(name=u.first_name or "студент", level=level, level_name=level_name),
            reply_markup=main_menu(level),
        )
    else:
        await message.answer(WELCOME_NEW, reply_markup=main_menu(None))


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, db: Database):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    level = user.get("level") if user else None
    await message.answer("🏫 <b>Главное меню</b>", reply_markup=main_menu(level))


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>Команды:</b>\n"
        "/start — начать / открыть приветствие\n"
        "/menu — главное меню\n"
        "/progress — ваша статистика\n"
        "/help — эта подсказка\n\n"
        "Всё обучение идёт через кнопки под сообщениями — ничего запоминать не нужно."
    )
    await message.answer(text)


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext, db: Database):
    await state.clear()
    user = await db.get_user(cb.from_user.id)
    level = user.get("level") if user else None
    await cb.message.edit_text("🏫 <b>Главное меню</b>", reply_markup=main_menu(level))
    await cb.answer()


# ───────── manual level picker ─────────

@router.callback_query(F.data == "level:choose")
async def cb_choose_level(cb: CallbackQuery):
    text = (
        "📘 <b>Выберите ваш уровень вручную:</b>\n\n"
        "Если сомневаетесь — лучше пройти тест. Он займёт пару минут."
    )
    await cb.message.edit_text(text, reply_markup=level_picker())
    await cb.answer()


@router.callback_query(F.data.startswith("level:set:"))
async def cb_set_level(cb: CallbackQuery, db: Database):
    code = cb.data.split(":")[-1]
    if code not in LEVELS:
        await cb.answer("Неизвестный уровень", show_alert=True)
        return
    await db.set_level(cb.from_user.id, code)
    info = LEVELS[code]
    text = (
        f"✅ Уровень установлен: <b>{code} — {info.name}</b>\n\n"
        f"{info.description}\n\n"
        "Нажмите «📚 Урок дня», чтобы начать."
    )
    await cb.message.edit_text(text, reply_markup=main_menu(code))
    await cb.answer("Отлично!")


# Generic "cancel into menu" hook used by FSMs
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    level = user.get("level") if user else None
    await message.answer("Отменено. Возвращаемся в меню.", reply_markup=main_menu(level))
