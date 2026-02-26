from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.core.exec import safe_html
from app.services.git import git_pull
from app.services.audit import log_action


router = Router()


@router.message(F.text == "🚀 GIT PULL")
async def git_pull_msg(message: types.Message, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    msg = await message.answer("⏳ <i>Git Pull...</i>", parse_mode="HTML")

    pull_res, log1, updated = git_pull(target, ctx=ctx)
    icon = "✅" if (updated or "Already up to date" in pull_res) else "⚠️"

    # Audit log
    log_action(
        user_id=message.from_user.id,
        action="git_pull",
        target=target.key,
        status="updated" if updated else "no_changes",
        repo_root=ctx.repo_root,
        details=log1[:100],  # Перші 100 символів коміт-повідомлення
    )

    text = (
        f"{icon} <b>ОНОВЛЕННЯ GIT</b> ({target.key})\n"
        f"🔖 {safe_html(log1, max_len=ctx.config.max_output_size)}\n"
        f"<blockquote expandable>{safe_html(pull_res, max_len=ctx.config.max_output_size)}</blockquote>"
    )
    await msg.edit_text(text, parse_mode="HTML")

    if updated:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=f"🔄 Перезапуск {target.service}", callback_data="confirm_restart"),
                    InlineKeyboardButton(text=f"🤖 Перезапуск {ctx.config.self_service_name}", callback_data="restart_self"),
                ]
            ]
        )
        await message.answer("✅ Код оновився. Який сервіс перезапустити?", reply_markup=kb)
