from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.core.exec import safe_html
from app.core.files import read_file, write_file
from app.services.pip import pip_freeze, pip_install, pip_outdated


router = Router()


class PipState(StatesGroup):
    waiting_for_new_reqs = State()


@router.message(F.text == "📦 PIP")
async def pip_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 requirements.txt", callback_data="pip_view"),
                InlineKeyboardButton(text="✏️ Редагувати", callback_data="pip_edit"),
            ],
            [InlineKeyboardButton(text="🔄 ВСТАНОВИТИ", callback_data="pip_install")],
            [
                InlineKeyboardButton(text="📦 freeze", callback_data="pip_freeze"),
                InlineKeyboardButton(text="🔍 outdated", callback_data="pip_outdated"),
            ],
        ]
    )
    await message.answer("📦 <b>PIP</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "pip_view")
async def pip_view_cb(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    content = read_file(target.resolved_req_file()) or "(порожньо)"
    await cb.message.answer(
        f"📄 <b>requirements.txt</b> ({target.key})\n<pre>{safe_html(content, max_len=ctx.config.max_output_size)}</pre>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "pip_edit")
async def pip_edit_start(cb: CallbackQuery, state: FSMContext, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    content = read_file(target.resolved_req_file())

    await state.set_state(PipState.waiting_for_new_reqs)
    await cb.message.answer(
        f"✏️ Надішліть НОВИЙ вміст requirements.txt для <code>{target.key}</code>. Він замінить старий.",
        parse_mode="HTML",
    )
    if content:
        await cb.message.answer(f"<code>{safe_html(content, max_len=ctx.config.max_output_size)}</code>", parse_mode="HTML")
    await cb.answer()


@router.message(PipState.waiting_for_new_reqs)
async def pip_edit_save(message: types.Message, state: FSMContext, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    if write_file(target.resolved_req_file(), message.text):
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Запустити встановлення", callback_data="pip_install")]])
        await message.answer("✅ <b>Файл збережено!</b>", reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer("❌ Помилка збереження файлу")


@router.callback_query(F.data == "pip_install")
async def pip_install_cb(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    msg = await cb.message.answer("⏳ <i>pip install...</i>", parse_mode="HTML")
    out = pip_install(target, ctx=ctx)
    await msg.edit_text(
        f"📦 <b>pip install</b> ({target.key})\n<blockquote expandable>{safe_html(out, max_len=ctx.config.max_output_size)}</blockquote>",
        parse_mode="HTML",
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Перезапустити сервіс", callback_data="confirm_restart")]])
    await cb.message.answer("Рекомендується перезапустити сервіс.", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "pip_freeze")
async def pip_freeze_cb(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    msg = await cb.message.answer("⏳", parse_mode="HTML")
    out = pip_freeze(target, ctx=ctx)
    await msg.edit_text(
        f"📦 <b>pip freeze</b> ({target.key})\n<blockquote expandable>{safe_html(out, max_len=ctx.config.max_output_size)}</blockquote>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "pip_outdated")
async def pip_outdated_cb(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    msg = await cb.message.answer("⏳ <i>Перевіряю...</i>", parse_mode="HTML")
    out = pip_outdated(target, ctx=ctx)

    text = (
        f"✅ Всі пакети актуальні ({target.key})"
        if "Package" not in out
        else f"🔍 <b>Outdated</b> ({target.key})\n<blockquote expandable>{safe_html(out, max_len=ctx.config.max_output_size)}</blockquote>"
    )
    await msg.edit_text(text, parse_mode="HTML")
    await cb.answer()
