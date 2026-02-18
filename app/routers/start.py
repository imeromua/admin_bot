from aiogram import Router, types
from aiogram.filters import Command

from app.context import Context
from app.core.exec import safe_html
from app.ui.keyboards import main_keyboard


router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    repo_line = f"\n🔗 Repo: <code>{safe_html(target.repo, max_len=ctx.config.max_output_size)}</code>" if target.repo else ""

    await message.answer(
        "⚙️ <b>Admin Panel для керування ботами</b>\n\n"
        f"🎯 Target: <code>{target.key}</code>\n"
        f"📦 Service: <code>{target.service}</code>\n"
        f"📁 Path: <code>{safe_html(str(target.path), max_len=ctx.config.max_output_size)}</code>"
        f"{repo_line}\n"
        f"🤖 Self service: <code>{ctx.config.self_service_name}</code>\n\n"
        "🎯 <b>Основні функції:</b>\n"
        "• 📊 Моніторинг статусу сервісу\n"
        "• 📜 Перегляд логів (50/100/200 записів)\n"
        "• 🔥 Фільтрація: Critical/Errors/Warnings/Timeframes\n"
        "• 🚨 <b>Automated alerts</b> з швидкими діями\n"
        "• 📝 <b>Audit log</b> всіх адмін-дій\n"
        "• ⚙️ Системна інформація (CPU, RAM, Disk)\n"
        "• 🔧 Управління ENV змінними\n"
        "• 📦 PIP менеджер (install, freeze, outdated)\n"
        "• 🚀 Git pull та автоматичний restart\n"
        "• 💾 Backup PostgreSQL/Redis\n\n"
        "🔐 Доступ тільки для адміністраторів\n"
        "🏭 Сервер: NETX\n"
        "🏭 <b>Build: v6.1 DevOps Enhanced</b>\n\n"
        "Оберіть команду з меню:",
        reply_markup=main_keyboard(target),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "ℹ️ <b>Help - Admin Bot v6.1</b>\n\n"
        "<b>📜 Логи:</b>\n"
        "• 50/100/200 рядків або сьогоднішні\n"
        "• 🔥 Critical (10) - тільки критичні помилки\n"
        "• 🚨 Errors (50) / ⚠️ Warnings (50)\n"
        "• ⏰ Timeframes: 1год / 3год / 24год\n"
        "• 📥 Завантажити відфільтровані\n\n"
        "<b>🚨 Alerts (v6.1):</b>\n"
        "• Автоматичні сповіщення про проблеми\n"
        "• ✅ Виправляємо - помітити як 'в роботі'\n"
        "• 🔄 Restart - швидкий рестарт\n"
        "• 📜 Повні логи - останні 50 рядків\n\n"
        "<b>📝 Audit:</b>\n"
        "• /audit - перегляд історії дій\n"
        "• Записуються: restart, git pull, alerts\n\n"
        "<b>🎯 Інше:</b>\n"
        "• 🎯 Бот - обрати ціль (generator/inventory)\n"
        "• 🚀 GIT PULL - оновити код + restart\n"
        "• 🤖 Self-restart - оновити admin_bot\n"
        "• ⚙️ /sysinfo - CPU, RAM, Disk warnings",
        parse_mode="HTML",
    )
