import re
from pathlib import Path
from typing import List

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile

from app.context import Context
from app.core.exec import safe_html
from app.services.journal import journalctl_lines


router = Router()


@router.message(F.text == "📜 Логи")
async def logs_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 50", callback_data="logs:50"),
                InlineKeyboardButton(text="📋 100", callback_data="logs:100"),
                InlineKeyboardButton(text="📋 200", callback_data="logs:200"),
            ],
            [InlineKeyboardButton(text="📅 Сьогодні", callback_data="logs:today")],
            [
                InlineKeyboardButton(text="🚨 Помилки (50)", callback_data="logs:errors:50"),
                InlineKeyboardButton(text="⚠️ Warnings (50)", callback_data="logs:warnings:50"),
            ],
            [InlineKeyboardButton(text="💾 Завантажити файл", callback_data="logs:download")],
        ]
    )
    await message.answer("📜 <b>Логи (journalctl)</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("logs:"))
async def logs_view(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    parts = cb.data.split(":")

    if cb.data == "logs:today":
        out = journalctl_lines(target.service, since="today", ctx=ctx)
        title = f"📅 Логи за сьогодні ({target.key})"
    elif cb.data == "logs:download":
        await cb.answer("⏳ Генерую файл...", show_alert=True)
        out = journalctl_lines(target.service, n=500, ctx=ctx)
        filename = Path(f"logs_{target.key}.txt")
        filename.write_text(out + "\n", encoding="utf-8")
        await cb.message.answer_document(FSInputFile(str(filename)))
        filename.unlink(missing_ok=True)
        return
    elif len(parts) == 2 and parts[1].isdigit():
        n = int(parts[1])
        out = journalctl_lines(target.service, n=n, ctx=ctx)
        title = f"📋 Останні {n} ({target.key})"
    elif len(parts) == 3 and parts[1] in {"errors", "warnings"} and parts[2].isdigit():
        level = parts[1]
        n = int(parts[2])
        raw = journalctl_lines(target.service, n=500, ctx=ctx)
        lines = raw.splitlines()
        if level == "errors":
            pattern = re.compile(r"ERROR|CRITICAL|Exception|Traceback", re.IGNORECASE)
            filtered = [ln for ln in lines if pattern.search(ln)]
            title = f"🚨 Помилки (останні {n}) ({target.key})"
        else:
            pattern = re.compile(r"warning", re.IGNORECASE)
            filtered = [ln for ln in lines if pattern.search(ln)]
            title = f"⚠️ Warnings (останні {n}) ({target.key})"
        out = "\n".join(filtered[-n:]) or "(немає збігів)"
    else:
        await cb.answer()
        return

    if not out or out.startswith("❌"):
        await cb.message.answer(f"{title}\n\n❌ Логи недоступні або порожні")
        await cb.answer()
        return

    chunks: List[str] = []
    cur = ""
    for line in out.split("\n"):
        if len(cur) + len(line) + 1 > 3800:
            chunks.append(cur)
            cur = line
        else:
            cur += line + "\n"
    if cur:
        chunks.append(cur)

    max_len = ctx.config.max_output_size
    await cb.message.answer(
        f"{title}\n<blockquote expandable>{safe_html(chunks[0], max_len=max_len)}</blockquote>",
        parse_mode="HTML",
    )
    for ch in chunks[1:]:
        await cb.message.answer(
            f"<blockquote expandable>{safe_html(ch, max_len=max_len)}</blockquote>",
            parse_mode="HTML",
        )

    await cb.answer()
