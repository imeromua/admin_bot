import asyncio

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.core.exec import safe_html
from app.services.self_update import self_git_update
from app.services.systemd import sudo_systemctl_restart


router = Router()


BTN_SELF_UPDATE = "🤖 Оновити admin_bot"


@router.message(F.text == BTN_SELF_UPDATE)
async def self_update_btn(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm_self_update"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_self_update"),
            ]
        ]
    )
    await message.answer(
        "⚠️ <b>Підтвердіть оновлення admin_bot</b>\n"
        "Я підтягну код з git та перезапущу сервіс <code>admin_bot</code>.\n"
        "Після цього бот буде тимчасово недоступний (10–15 секунд).",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm_self_update")
async def confirm_self_update(cb: CallbackQuery, ctx: Context):
    msg = await cb.message.edit_text("⏳ <i>Оновлюю admin_bot з git...</i>", parse_mode="HTML")

    res, log1, updated = await asyncio.to_thread(self_git_update, ctx=ctx)
    icon = "✅" if updated else "ℹ️"

    text = (
        f"{icon} <b>САМООНОВЛЕННЯ</b>\n"
        f"🔖 {safe_html(log1, max_len=ctx.config.max_output_size)}\n"
        f"<blockquote expandable>{safe_html(res, max_len=ctx.config.max_output_size)}</blockquote>\n\n"
        f"🤖 Перезапускаю <code>{ctx.config.self_service_name}</code>..."
    )
    await msg.edit_text(text, parse_mode="HTML")
    await cb.answer()

    asyncio.create_task(_delayed_self_restart(ctx))


@router.callback_query(F.data == "cancel_self_update")
async def cancel_self_update(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer("Скасовано")


async def _delayed_self_restart(ctx: Context):
    await asyncio.sleep(1)
    await asyncio.to_thread(sudo_systemctl_restart, ctx.config.self_service_name, ctx=ctx)
