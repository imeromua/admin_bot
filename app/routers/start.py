from aiogram import Router, types
from aiogram.filters import Command

from app.context import Context
from app.core.exec import safe_html
from app.ui.keyboards import main_keyboard


router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    repo_line = f"\n🔗 Репозиторій: <code>{safe_html(target.repo, max_len=ctx.config.max_output_size)}</code>" if target.repo else ""

    await message.answer(
        "⚙️ <b>Панель адміністратора для керування ботами</b>\n\n"
        f"🎯 Ціль: <code>{target.key}</code>\n"
        f"📦 Сервіс: <code>{target.service}</code>\n"
        f"📁 Шлях: <code>{safe_html(str(target.path), max_len=ctx.config.max_output_size)}</code>"
        f"{repo_line}\n"
        f"🤖 Власний сервіс: <code>{ctx.config.self_service_name}</code>\n\n"
        "🎯 <b>Основні функції:</b>\n"
        "• 📊 Моніторинг статусу сервісу\n"
        "• 📜 Перегляд логів (50/100/200 записів)\n"
        "• 🔥 Фільтрація: Критичні/Помилки/Попередження/Часові рамки\n"
        "• 🚨 <b>Автоматичні сповіщення</b> зі швидкими діями\n"
        "• 📝 <b>Журнал аудиту</b> всіх адмін-дій\n"
        "• ⚙️ Системна інформація (CPU, RAM, Диск)\n"
        "• 🔧 Управління ENV змінними\n"
        "• 📦 PIP менеджер (встановлення, перелік, застарілі)\n"
        "• 🚀 Git pull та автоматичний перезапуск\n"
        "• 💾 Резервне копіювання PostgreSQL/Redis\n\n"
        "🔐 Доступ тільки для адміністраторів\n"
        "🏭 Сервер: NETX\n"
        "🏭 <b>Збірка: v6.2</b>\n\n"
        "Оберіть команду з меню:",
        reply_markup=main_keyboard(target),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "ℹ️ <b>Довідка — Адмін Бот v6.2</b>\n\n"
        "<b>📜 Логи:</b>\n"
        "• 50/100/200 рядків або сьогоднішні\n"
        "• 🔥 Критичні (10) — тільки критичні помилки\n"
        "• 🚨 Помилки (50) / ⚠️ Попередження (50)\n"
        "• ⏰ Часові рамки: 1год / 3год / 24год\n"
        "• 📥 Завантажити відфільтровані\n\n"
        "<b>🚨 Сповіщення (v6.1):</b>\n"
        "• Автоматичні сповіщення про проблеми\n"
        "• ✅ Виправляємо — помітити як 'в роботі'\n"
        "• 🔄 Перезапуск — швидкий рестарт\n"
        "• 📜 Повні логи — останні 50 рядків\n\n"
        "<b>📝 Аудит:</b>\n"
        "• /audit — перегляд історії дій\n"
        "• Записуються: перезапуск, git pull, сповіщення\n\n"
        "<b>🎯 Інше:</b>\n"
        "• 🎯 Бот — обрати ціль (generator/inventory)\n"
        "• 🚀 GIT PULL — оновити код + перезапуск\n"
        "• 🤖 Самооновлення — оновити admin_bot\n"
        "• ⚙️ /sysinfo — CPU, RAM, попередження про диск",
        parse_mode="HTML",
    )
