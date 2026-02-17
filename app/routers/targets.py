from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.ui.keyboards import main_keyboard


router = Router()


@router.message(F.text == "🎯 Бот")
async def target_menu(message: types.Message, ctx: Context):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{t.key} ({t.service})", callback_data=f"target:{t.key}")]
            for t in ctx.targets.values()
        ]
    )
    await message.answer("🎯 <b>Оберіть бота</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("target:"))
async def target_set(cb: CallbackQuery, ctx: Context):
    key = cb.data.split(":", 1)[1]
    ctx.set_active_target(cb.message.chat.id, key)
    target = ctx.get_active_target(cb.message.chat.id)

    await cb.message.answer(
        f"✅ Активна ціль: <code>{target.key}</code>",
        reply_markup=main_keyboard(target),
        parse_mode="HTML",
    )
    await cb.answer()
