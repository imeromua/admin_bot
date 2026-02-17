from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.core.exec import safe_html
from app.services.db import get_db_status
from app.services.redis import get_redis_status
from app.services.systemd import systemctl_status


router = Router()


@router.message(F.text == "📊 Статус")
async def status_menu(message, ctx: Context):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Сервіс", callback_data="status:service")],
            [InlineKeyboardButton(text="🗄 PostgreSQL", callback_data="status:db")],
            [InlineKeyboardButton(text="🧠 Redis", callback_data="status:redis")],
        ]
    )
    await message.answer("📊 <b>Статус</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("status:"))
async def status_view(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    _, what = cb.data.split(":", 1)

    if what == "service":
        raw = systemctl_status(target.service, ctx=ctx)
        is_active = "active (running)" in raw
        icon = "🟢" if is_active else "🔴"
        await cb.message.answer(
            f"{icon} <b>Service</b> (<code>{target.service}</code>)\n"
            f"Target: <code>{target.key}</code>\n"
            f"<blockquote expandable>{safe_html(raw[:3000], max_len=ctx.config.max_output_size)}</blockquote>",
            parse_mode="HTML",
        )
    elif what == "db":
        await cb.message.answer(get_db_status(target, ctx=ctx), parse_mode="HTML")
    elif what == "redis":
        await cb.message.answer(get_redis_status(target, ctx=ctx), parse_mode="HTML")

    await cb.answer()
