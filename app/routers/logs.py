import re
import tempfile
from pathlib import Path

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile

from app.context import Context
from app.core.exec import safe_html, split_text_chunks
from app.services.journal import journalctl_lines


router = Router()

# ── відображення часових міток ──────────────────────────────────────────
_SINCE_MAP = {
    "5m":  "5 minutes ago",
    "10m": "10 minutes ago",
    "20m": "20 minutes ago",
    "1h":  "1 hour ago",
    "5h":  "5 hours ago",
    "12h": "12 hours ago",
}

_LABEL_MAP = {
    "5m":  "5 хв",
    "10m": "10 хв",
    "20m": "20 хв",
    "1h":  "1 год",
    "5h":  "5 год",
    "12h": "12 год",
}

# ── патерни фільтрації ──────────────────────────────────────────────────
_PATTERNS = {
    "errors":   re.compile(r"ERROR|CRITICAL|Exception|Traceback", re.IGNORECASE),
    "warnings": re.compile(r"warning", re.IGNORECASE),
}


def _filter_lines(raw: str, level: str) -> str:
    """Повертає рядки журналу, що відповідають рівню level."""
    pattern = _PATTERNS.get(level)
    if pattern is None:
        return raw
    filtered = [ln for ln in raw.splitlines() if pattern.search(ln)]
    return "\n".join(filtered)


@router.message(F.text == "📜 Логи")
async def logs_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            # ── всі логи — переглянути ──
            [
                InlineKeyboardButton(text="📋 Всі (5 хв)",  callback_data="logs:view:all:5m"),
                InlineKeyboardButton(text="📋 Всі (10 хв)", callback_data="logs:view:all:10m"),
                InlineKeyboardButton(text="📋 Всі (20 хв)", callback_data="logs:view:all:20m"),
            ],
            # ── всі логи — завантажити ──
            [
                InlineKeyboardButton(text="📥 Всі (5 хв)",  callback_data="logs:dl:all:5m"),
                InlineKeyboardButton(text="📥 Всі (10 хв)", callback_data="logs:dl:all:10m"),
                InlineKeyboardButton(text="📥 Всі (20 хв)", callback_data="logs:dl:all:20m"),
            ],
            # ── помилки — переглянути ──
            [
                InlineKeyboardButton(text="🚨 Помилки (5 хв)",  callback_data="logs:view:errors:5m"),
                InlineKeyboardButton(text="🚨 Помилки (10 хв)", callback_data="logs:view:errors:10m"),
                InlineKeyboardButton(text="🚨 Помилки (20 хв)", callback_data="logs:view:errors:20m"),
            ],
            # ── помилки — завантажити ──
            [
                InlineKeyboardButton(text="📥 Помилки (5 хв)",  callback_data="logs:dl:errors:5m"),
                InlineKeyboardButton(text="📥 Помилки (10 хв)", callback_data="logs:dl:errors:10m"),
                InlineKeyboardButton(text="📥 Помилки (20 хв)", callback_data="logs:dl:errors:20m"),
            ],
            # ── попередження — переглянути ──
            [
                InlineKeyboardButton(text="⚠️ Попередження (5 хв)",  callback_data="logs:view:warnings:5m"),
                InlineKeyboardButton(text="⚠️ Попередження (10 хв)", callback_data="logs:view:warnings:10m"),
                InlineKeyboardButton(text="⚠️ Попередження (20 хв)", callback_data="logs:view:warnings:20m"),
            ],
            # ── попередження — завантажити ──
            [
                InlineKeyboardButton(text="📥 Попередження (5 хв)",  callback_data="logs:dl:warnings:5m"),
                InlineKeyboardButton(text="📥 Попередження (10 хв)", callback_data="logs:dl:warnings:10m"),
                InlineKeyboardButton(text="📥 Попередження (20 хв)", callback_data="logs:dl:warnings:20m"),
            ],
            # ── скачати всі логи за годину ──
            [
                InlineKeyboardButton(text="📥 Скачати (1 год)",  callback_data="logs:dl:all:1h"),
                InlineKeyboardButton(text="📥 Скачати (5 год)",  callback_data="logs:dl:all:5h"),
                InlineKeyboardButton(text="📥 Скачати (12 год)", callback_data="logs:dl:all:12h"),
            ],
        ]
    )
    await message.answer("📜 <b>Логи (journalctl)</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("logs:"))
async def logs_view(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    parts = cb.data.split(":")

    # очікуємо формат logs:<action>:<level>:<timeframe>
    if len(parts) != 4:
        await cb.answer()
        return

    _, action, level, timeframe = parts

    since = _SINCE_MAP.get(timeframe)
    label = _LABEL_MAP.get(timeframe, timeframe)

    if since is None or action not in {"view", "dl"}:
        await cb.answer()
        return

    raw = journalctl_lines(target.service, since=since, ctx=ctx)

    if level in _PATTERNS:
        out = _filter_lines(raw, level) or "(немає збігів)"
    else:
        out = raw

    icon = "🚨" if level == "errors" else "⚠️" if level == "warnings" else "📋"
    lvl_name = "помилки" if level == "errors" else "попередження" if level == "warnings" else "всі"

    if action == "dl":
        await cb.answer("⏳ Генерую файл…", show_alert=True)

        if not out or out.startswith("❌"):
            await cb.message.answer("❌ Логи недоступні або порожні")
            return

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix=f"logs_{level}_{target.key}_", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(out + "\n")
            tmp_path = Path(tmp.name)

        caption = f"{icon} Логи ({lvl_name}) — останні {label} ({target.key})"
        await cb.message.answer_document(FSInputFile(str(tmp_path)), caption=caption)
        tmp_path.unlink(missing_ok=True)
        return

    # action == "view"
    title = f"{icon} Логи ({lvl_name}) за останні {label} ({target.key})"

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
