import asyncio
import subprocess
from pathlib import Path

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.core.exec import safe_html
from app.services.audit import log_action

router = Router()


def _get_frontend_path(target) -> Path | None:
    """Шлях до frontend/ — сусідня папка з PATH цілі або явно задана через _FRONTEND_PATH."""
    import os
    key = target.key.upper()
    explicit = os.getenv(f"ADMIN_TARGET_{key}_FRONTEND_PATH")
    if explicit:
        return Path(explicit)
    # Якщо PATH цілі — корінь репо, шукаємо frontend/ поруч
    candidate = target.path / "frontend"
    if candidate.exists():
        return candidate
    return None


@router.message(F.text == "🏗 BUILD")
async def frontend_build_btn(message: types.Message, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    frontend_path = _get_frontend_path(target)

    if not frontend_path:
        await message.answer(
            f"⚠️ Для цілі <code>{target.key}</code> не знайдено папку <code>frontend/</code>.\n"
            f"Додайте <code>ADMIN_TARGET_{target.key.upper()}_FRONTEND_PATH</code> у .env",
            parse_mode="HTML",
        )
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm_build"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_build"),
            ]
        ]
    )
    await message.answer(
        f"🏗 <b>Збірка фронтенду</b>\n"
        f"Шлях: <code>{frontend_path}</code>\n"
        f"Команда: <code>npm run build</code>",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm_build")
async def confirm_build(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    frontend_path = _get_frontend_path(target)

    if not frontend_path:
        await cb.message.edit_text("❌ Шлях до frontend не знайдено.")
        await cb.answer()
        return

    msg = await cb.message.edit_text(
        f"🏗 Збираю фронтенд...\n<code>{frontend_path}</code>",
        parse_mode="HTML",
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            "npm", "run", "build",
            cwd=str(frontend_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        output = stdout.decode(errors="replace")
        success = proc.returncode == 0
    except asyncio.TimeoutError:
        output = "Перевищено час очікування (5 хв)"
        success = False
    except Exception as e:
        output = str(e)
        success = False

    # Обрізаємо вивід до ліміту
    max_len = ctx.config.max_output_size - 200
    if len(output) > max_len:
        output = "..." + output[-max_len:]

    log_action(
        user_id=cb.from_user.id,
        action="frontend_build",
        target=target.key,
        status="success" if success else "failed",
        repo_root=ctx.repo_root,
        details=f"cwd={frontend_path}",
    )

    icon = "✅" if success else "❌"
    await msg.edit_text(
        f"{icon} <b>{'Збірка успішна' if success else 'Збірка провалилась'}</b>\n"
        f"<pre>{safe_html(output, max_len=max_len)}</pre>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "cancel_build")
async def cancel_build(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer("Скасовано")
