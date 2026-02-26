import re
import tempfile
from pathlib import Path

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile

from app.context import Context
from app.core.exec import safe_html, split_text_chunks
from app.services.journal import journalctl_lines


router = Router()


@router.message(F.text == "📜 Логи")
async def logs_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 50",  callback_data="logs:50"),
                InlineKeyboardButton(text="📋 100", callback_data="logs:100"),
                InlineKeyboardButton(text="📋 200", callback_data="logs:200"),
            ],
            [InlineKeyboardButton(text="📅 Сьогодні", callback_data="logs:today")],
            [
                InlineKeyboardButton(text="🔥 Критичні (10)", callback_data="logs:critical:10"),
                InlineKeyboardButton(text="🚨 Помилки (50)",  callback_data="logs:errors:50"),
            ],
            [
                InlineKeyboardButton(text="⚠️ Попередження (50)", callback_data="logs:warnings:50"),
            ],
            # ── фільтр за часом ──
            [
                InlineKeyboardButton(text="⏰ 1 год",  callback_data="logs:timeframe:1h"),
                InlineKeyboardButton(text="⏰ 3 год",  callback_data="logs:timeframe:3h"),
                InlineKeyboardButton(text="⏰ 24 год", callback_data="logs:timeframe:24h"),
            ],
            [InlineKeyboardButton(text="💾 Завантажити файл", callback_data="logs:download")],
            # ── завантаження відфільтрованих ──
            [
                InlineKeyboardButton(text="📥 Критичні 10", callback_data="logs:dl_critical:10"),
                InlineKeyboardButton(text="📥 Критичні 20", callback_data="logs:dl_critical:20"),
            ],
            [
                InlineKeyboardButton(text="📥 Помилки 20",  callback_data="logs:dl_errors:20"),
                InlineKeyboardButton(text="📥 Помилки 30",  callback_data="logs:dl_errors:30"),
                InlineKeyboardButton(text="📥 Помилки 50",  callback_data="logs:dl_errors:50"),
            ],
            [
                InlineKeyboardButton(text="📥 Попередження 20", callback_data="logs:dl_warnings:20"),
                InlineKeyboardButton(text="📥 Попередження 30", callback_data="logs:dl_warnings:30"),
                InlineKeyboardButton(text="📥 Попередження 50", callback_data="logs:dl_warnings:50"),
            ],
        ]
    )
    await message.answer("📜 <b>Логи (journalctl)</b>", reply_markup=kb, parse_mode="HTML")


# ── патерни фільтрації ──────────────────────────────────────────────────
_PATTERNS = {
    "critical": re.compile(r"CRITICAL|FATAL|Traceback", re.IGNORECASE),
    "errors":   re.compile(r"ERROR|CRITICAL|Exception|Traceback", re.IGNORECASE),
    "warnings": re.compile(r"warning", re.IGNORECASE),
}


def _filter_lines(raw: str, level: str, n: int) -> str:
    """Повертає останні n рядків відфільтрованого журналу або порожній рядок."""
    pattern = _PATTERNS[level]
    filtered = [ln for ln in raw.splitlines() if pattern.search(ln)]
    return "\n".join(filtered[-n:])


@router.callback_query(F.data.startswith("logs:"))
async def logs_view(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    parts = cb.data.split(":")

    # ── скачування відфільтрованих логів (errors / warnings / critical) ──
    if len(parts) == 3 and parts[1] in {"dl_errors", "dl_warnings", "dl_critical"} and parts[2].isdigit():
        level_key = parts[1].replace("dl_", "")   # "errors", "warnings" або "critical"
        n = int(parts[2])

        await cb.answer(f"⏳ Генерую файл ({level_key}, {n} рядків)…", show_alert=True)

        raw = journalctl_lines(target.service, n=1000, ctx=ctx)
        filtered = _filter_lines(raw, level_key, n)

        icon = "🔥" if level_key == "critical" else ("🚨" if level_key == "errors" else "⚠️")
        if not filtered:
            await cb.message.answer(f"{icon} Немає записів ({level_key}) для {target.key}")
            return

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix=f"{level_key}_{target.key}_", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(filtered + "\n")
            tmp_path = Path(tmp.name)

        caption = f"{icon} {level_key.capitalize()} — останні {n} рядків ({target.key})"
        await cb.message.answer_document(FSInputFile(str(tmp_path)), caption=caption)
        tmp_path.unlink(missing_ok=True)
        return

    # ── фільтр за timeframe ───────────────────────────────────────────────
    if len(parts) == 3 and parts[1] == "timeframe":
        timeframe = parts[2]  # "1h", "3h", "24h"
        since_map = {"1h": "1 hour ago", "3h": "3 hours ago", "24h": "1 day ago"}
        since = since_map.get(timeframe, "1 hour ago")
        
        out = journalctl_lines(target.service, since=since, ctx=ctx)
        title = f"⏰ Логи за останні {timeframe.replace('h', ' год')} ({target.key})"
    # ── critical фільтр ─────────────────────────────────────────────────────
    elif len(parts) == 3 and parts[1] == "critical" and parts[2].isdigit():
        n = int(parts[2])
        raw = journalctl_lines(target.service, n=1000, ctx=ctx)
        filtered_text = _filter_lines(raw, "critical", n)
        out = filtered_text or "(немає збігів)"
        title = f"🔥 Critical (останні {n}) ({target.key})"
    # ── решта існуючої логіки ──────────────────────────────────────────────
    elif cb.data == "logs:today":
        out = journalctl_lines(target.service, since="today", ctx=ctx)
        title = f"📅 Логи за сьогодні ({target.key})"
    elif cb.data == "logs:download":
        await cb.answer("⏳ Генерую файл...", show_alert=True)
        out = journalctl_lines(target.service, n=500, ctx=ctx)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix=f"logs_{target.key}_", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(out + "\n")
            tmp_path = Path(tmp.name)

        await cb.message.answer_document(FSInputFile(str(tmp_path)))
        tmp_path.unlink(missing_ok=True)
        return
    elif len(parts) == 2 and parts[1].isdigit():
        n = int(parts[1])
        out = journalctl_lines(target.service, n=n, ctx=ctx)
        title = f"📋 Останні {n} ({target.key})"
    elif len(parts) == 3 and parts[1] in {"errors", "warnings"} and parts[2].isdigit():
        level = parts[1]
        n = int(parts[2])
        raw = journalctl_lines(target.service, n=500, ctx=ctx)
        filtered_text = _filter_lines(raw, level, n)
        out = filtered_text or "(немає збігів)"
        title = (
            f"🚨 Помилки (останні {n}) ({target.key})"
            if level == "errors"
            else f"⚠️ Попередження (останні {n}) ({target.key})"
        )
    else:
        await cb.answer()
        return

    if not out or out.startswith("❌"):
        await cb.message.answer(f"{title}\n\n❌ Логи недоступні або порожні")
        await cb.answer()
        return

    chunks = split_text_chunks(out)
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
