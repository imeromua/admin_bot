import asyncio

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.core.exec import safe_html
from app.services.systemd import sudo_systemctl_restart, systemctl_is_active
from app.services.audit import log_action


router = Router()


@router.message(F.text == "🔄 RESTART")
async def restart_btn(message: types.Message, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm_restart"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_restart"),
            ]
        ]
    )
    await message.answer(
        f"⚠️ <b>Підтвердіть перезапуск</b>\nСервіс <code>{target.service}</code> буде перезапущено.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm_restart")
async def confirm_restart(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    msg = await cb.message.edit_text(f"🔄 Перезапускаю <code>{target.service}</code>...", parse_mode="HTML")

    sudo_systemctl_restart(target.service, ctx=ctx)
    await asyncio.sleep(3)

    status = systemctl_is_active(target.service, ctx=ctx)
    is_success = status.strip() == "active"
    
    # Audit log
    log_action(
        user_id=cb.from_user.id,
        action="restart",
        target=target.service,
        status="success" if is_success else "failed",
        repo_root=ctx.repo_root,
        details=f"Status after restart: {status.strip()}",
    )

    text = "✅ <b>Перезапуск успішний!</b>" if is_success else f"⚠️ Status: <code>{safe_html(status, max_len=ctx.config.max_output_size)}</code>"
    await msg.edit_text(text, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "cancel_restart")
async def cancel_restart(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer("Скасовано")
