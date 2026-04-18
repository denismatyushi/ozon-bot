"""Inline keyboards for the main menu and common navigation."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.content.levels import LEVELS, LEVEL_ORDER


def main_menu(level: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if level is None:
        rows.append([InlineKeyboardButton(text="🎯 Пройти тест на уровень", callback_data="placement:start")])
        rows.append([InlineKeyboardButton(text="📘 Выбрать уровень вручную", callback_data="level:choose")])
    else:
        rows.append([InlineKeyboardButton(text="📚 Урок дня", callback_data="lesson:start")])
        rows.append([
            InlineKeyboardButton(text="🔤 Словарь (SRS)", callback_data="vocab:start"),
            InlineKeyboardButton(text="📖 Грамматика", callback_data="grammar:list"),
        ])
        rows.append([
            InlineKeyboardButton(text="📊 Прогресс", callback_data="progress"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
        ])
        rows.append([InlineKeyboardButton(text="🎯 Перепройти тест уровня", callback_data="placement:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
    ])


def level_picker() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{code} — {LEVELS[code].name}", callback_data=f"level:set:{code}")]
        for code in LEVEL_ORDER
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def answer_options(options: list[str], prefix: str) -> InlineKeyboardMarkup:
    """Inline keyboard where each option becomes a button; callback is prefix:i."""
    rows = [[InlineKeyboardButton(text=opt, callback_data=f"{prefix}:{i}")]
            for i, opt in enumerate(options)]
    return InlineKeyboardMarkup(inline_keyboard=rows)
