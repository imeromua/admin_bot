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
        "👋 <b>Admin Bot</b>\n\n"
        f"🎯 Target: <code>{target.key}</code>\n"
        f"📦 Service: <code>{target.service}</code>\n"
        f"📁 Path: <code>{safe_html(str(target.path), max_len=ctx.config.max_output_size)}</code>"
        f"{repo_line}\n"
        f"🤖 Self service: <code>{ctx.config.self_service_name}</code>\n\n"
        "Оберіть команду з меню:",
        reply_markup=main_keyboard(target),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "ℹ️ <b>Help</b>\n"
        "- 🎯 Бот: обрати ціль (generator/inventory).\n"
        "- 🚀 GIT PULL: оновити код цілі, потім перезапуск.\n"
        "- 🤖 Self-restart доступний після pull (кнопка).",
        parse_mode="HTML",
    )
