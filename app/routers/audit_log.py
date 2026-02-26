"""Маршрутизатор для перегляду журналу аудиту."""
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from pathlib import Path

from app.context import Context
from app.core.exec import safe_html, split_text_chunks
from app.services.audit import get_recent_logs


router = Router()


@router.message(Command("audit"))
async def cmd_audit(message: types.Message, ctx: Context):
    """Показати останні записи журналу аудиту."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 20 останніх", callback_data="audit:20"),
                InlineKeyboardButton(text="📋 50 останніх", callback_data="audit:50"),
            ],
            [
                InlineKeyboardButton(text="📥 Завантажити всі", callback_data="audit:download"),
            ],
        ]
    )
    await message.answer(
        "📝 <b>Журнал аудиту</b>\n\nВсі адміністративні дії записуються в audit.log",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("audit:"))
async def audit_view(cb: CallbackQuery, ctx: Context):
    parts = cb.data.split(":")

    if cb.data == "audit:download":
        await cb.answer("⏳ Генерую файл...", show_alert=True)
        log_file = ctx.repo_root / "audit.log"
        if not log_file.exists():
            await cb.message.answer("⚠️ Журнал аудиту порожній або не існує")
            return
        await cb.message.answer_document(
            FSInputFile(str(log_file)), caption="📝 Журнал аудиту (повна історія)"
        )
        return

    if len(parts) == 2 and parts[1].isdigit():
        limit = int(parts[1])
        logs = get_recent_logs(ctx.repo_root, limit=limit)

        if not logs or logs == "Журнал аудиту порожній.":
            await cb.message.answer("📝 <b>Журнал аудиту</b>\n\nЖодних записів немає.", parse_mode="HTML")
            await cb.answer()
            return

        # Розбиваємо на чанки якщо дуже довго
        chunks = split_text_chunks(logs)

        await cb.message.answer(
            f"📝 <b>Журнал аудиту (останні {limit})</b>\n\n"
            f"<blockquote expandable>{safe_html(chunks[0], max_len=ctx.config.max_output_size)}</blockquote>",
            parse_mode="HTML",
        )
        for ch in chunks[1:]:
            await cb.message.answer(
                f"<blockquote expandable>{safe_html(ch, max_len=ctx.config.max_output_size)}</blockquote>",
                parse_mode="HTML",
            )

    await cb.answer()
