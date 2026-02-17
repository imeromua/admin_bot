from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.core.exec import safe_html
from app.core.envfile import parse_env_file, write_env_file


router = Router()


class EnvState(StatesGroup):
    waiting_for_value = State()
    waiting_for_new_key = State()
    waiting_for_new_value = State()


async def _show_env_menu(message_obj, ctx: Context, *, edit: bool = False):
    target = ctx.get_active_target(message_obj.chat.id)
    env_path = target.resolved_env_file()

    env_vars = parse_env_file(env_path)
    kb_rows = []
    for k, v in sorted(env_vars.items()):
        display_val = (v[:8] + "..") if len(v) > 10 else v
        kb_rows.append([InlineKeyboardButton(text=f"{k}={display_val}", callback_data=f"edit_env:{k}")])

    kb_rows.append([InlineKeyboardButton(text="➕ Нова змінна", callback_data="add_new_env")])
    kb_rows.append([InlineKeyboardButton(text="💾 Зберегти", callback_data="env_saved")])

    markup = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    title = f"🔧 <b>.env</b> ({target.key})\n<code>{safe_html(str(env_path), max_len=ctx.config.max_output_size)}</code>"

    if edit:
        await message_obj.edit_text(title, reply_markup=markup, parse_mode="HTML")
    else:
        await message_obj.answer(title, reply_markup=markup, parse_mode="HTML")


@router.message(F.text == "🔧 ENV")
async def env_menu(message: types.Message, ctx: Context):
    await _show_env_menu(message, ctx)


@router.callback_query(F.data.startswith("edit_env:"))
async def edit_env_var(cb: CallbackQuery, state: FSMContext, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    env_vars = parse_env_file(target.resolved_env_file())

    key = cb.data.split(":", 1)[1]
    await state.update_data(editing_key=key)
    await state.set_state(EnvState.waiting_for_value)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Скасувати", callback_data="cancel_env")]])
    await cb.message.edit_text(
        f"✏️ <b>{safe_html(key, max_len=ctx.config.max_output_size)}</b> ({target.key})\n"
        f"Зараз: <code>{safe_html(env_vars.get(key, ''), max_len=ctx.config.max_output_size)}</code>\n\n"
        "Надішліть нове значення:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(EnvState.waiting_for_value)
async def set_env_value(message: types.Message, state: FSMContext, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    data = await state.get_data()
    key = data.get("editing_key")

    env_path = target.resolved_env_file()
    env_vars = parse_env_file(env_path)
    env_vars[str(key)] = message.text.strip()
    write_env_file(env_path, env_vars)

    await state.clear()
    await _show_env_menu(message, ctx)


@router.callback_query(F.data == "add_new_env")
async def add_new_env_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EnvState.waiting_for_new_key)
    await cb.message.edit_text(
        "➕ Назва нової змінної:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Скасувати", callback_data="cancel_env")]]),
    )
    await cb.answer()


@router.message(EnvState.waiting_for_new_key)
async def add_new_env_key(message: types.Message, state: FSMContext, ctx: Context):
    key = message.text.strip().upper().replace(" ", "_")
    await state.update_data(new_key=key)
    await state.set_state(EnvState.waiting_for_new_value)
    await message.answer(f"Введіть значення для <code>{safe_html(key, max_len=ctx.config.max_output_size)}</code>:", parse_mode="HTML")


@router.message(EnvState.waiting_for_new_value)
async def add_new_env_value(message: types.Message, state: FSMContext, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    data = await state.get_data()
    key = data.get("new_key")

    env_path = target.resolved_env_file()
    env_vars = parse_env_file(env_path)
    env_vars[str(key)] = message.text.strip()
    write_env_file(env_path, env_vars)

    await state.clear()
    await message.answer("✅ Змінну додано!", parse_mode="HTML")
    await _show_env_menu(message, ctx)


@router.callback_query(F.data == "cancel_env")
async def cancel_env(cb: CallbackQuery, state: FSMContext, ctx: Context):
    await state.clear()
    await _show_env_menu(cb.message, ctx, edit=True)
    await cb.answer()


@router.callback_query(F.data == "env_saved")
async def env_saved(cb: CallbackQuery):
    await cb.answer("✅ Збережено")
