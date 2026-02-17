from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from app.core.targets import Target


def main_keyboard(target: Target) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Бот"), KeyboardButton(text="📊 Статус"), KeyboardButton(text="📜 Логи")],
            [KeyboardButton(text="📦 PIP"), KeyboardButton(text="🔧 ENV"), KeyboardButton(text="🚀 GIT PULL")],
            [KeyboardButton(text="🔄 RESTART"), KeyboardButton(text="💾 Бекап БД"), KeyboardButton(text="⚙️ Системна інфо")],
        ],
        resize_keyboard=True,
        input_field_placeholder=f"Target: {target.key}",
    )
