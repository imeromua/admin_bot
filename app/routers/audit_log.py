"""Router for viewing audit logs."""
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from pathlib import Path

from app.context import Context
from app.core.exec import safe_html
from app.services.audit import get_recent_logs


router = Router()


@router.message(Command("audit"))
async def cmd_audit(message: types.Message, ctx: Context):
    """Show recent audit log entries."""
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
        "📝 <b>Audit Log</b>\n\nВсі адміністративні дії записуються в audit.log",
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
            await cb.message.answer("⚠️ Audit log порожній або не існує")
            return
        await cb.message.answer_document(
            FSInputFile(str(log_file)), caption="📝 Audit log (повна історія)"
        )
        return

    if len(parts) == 2 and parts[1].isdigit():
        limit = int(parts[1])
        logs = get_recent_logs(ctx.repo_root, limit=limit)

        if not logs or logs == "Audit log is empty.":
            await cb.message.answer("📝 <b>Audit Log</b>\n\nЖодних записів немає.", parse_mode="HTML")
            await cb.answer()
            return

        # Розбиваємо на чанки якщо дуже довго
        chunks = []
        cur = ""
        for line in logs.split("\n"):
            if len(cur) + len(line) + 1 > 3800:
                chunks.append(cur)
                cur = line
            else:
                cur += line + "\n"
        if cur:
            chunks.append(cur)

        await cb.message.answer(
            f"📝 <b>Audit Log (останні {limit})</b>\n\n"
            f"<blockquote expandable>{safe_html(chunks[0], max_len=ctx.config.max_output_size)}</blockquote>",
            parse_mode="HTML",
        )
        for ch in chunks[1:]:
            await cb.message.answer(
                f"<blockquote expandable>{safe_html(ch, max_len=ctx.config.max_output_size)}</blockquote>",
                parse_mode="HTML",
            )

    await cb.answer()
