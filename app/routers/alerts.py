"""Router for handling alert quick actions."""
import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.context import Context
from app.core.exec import safe_html
from app.services.watchdog import acknowledge_alert
from app.services.systemd import sudo_systemctl_restart, systemctl_is_active
from app.services.journal import journalctl_lines
from app.services.audit import log_action


router = Router()


@router.callback_query(F.data.startswith("ack_alert:"))
async def acknowledge_alert_callback(cb: CallbackQuery, ctx: Context):
    """Помітити alert як 'в роботі' - більше не спамити."""
    alert_key = cb.data.replace("ack_alert:", "")
    
    # Помічаємо alert
    acknowledge_alert(alert_key)
    
    # Audit log
    log_action(
        user_id=cb.from_user.id,
        action="acknowledge_alert",
        target=alert_key,
        status="acknowledged",
        repo_root=ctx.repo_root,
        details="Помічено як 'в роботі', більше не спамити",
    )
    
    await cb.message.edit_text(
        cb.message.text + "\n\n✅ <b>Помічено як 'в роботі'</b>\nПовторні сповіщення про цю проблему відключено.",
        parse_mode="HTML",
    )
    await cb.answer("✅ Алерт помічено")


@router.callback_query(F.data.startswith("quick_restart:"))
async def quick_restart_callback(cb: CallbackQuery, ctx: Context):
    """Швидкий рестарт сервісу з alertу."""
    target_key = cb.data.replace("quick_restart:", "")
    
    if target_key not in ctx.targets:
        await cb.answer("❌ Ціль не знайдена", show_alert=True)
        return
    
    target = ctx.targets[target_key]
    
    await cb.answer("⏳ Рестарт...", show_alert=True)
    
    # Рестарт
    sudo_systemctl_restart(target.service, ctx=ctx)
    await asyncio.sleep(3)
    
    status = systemctl_is_active(target.service, ctx=ctx).strip()
    is_success = status == "active"
    
    # Audit log
    log_action(
        user_id=cb.from_user.id,
        action="quick_restart_from_alert",
        target=target.service,
        status="success" if is_success else "failed",
        repo_root=ctx.repo_root,
        details=f"Рестарт з alertу, статус: {status}",
    )
    
    icon = "✅" if is_success else "❌"
    result_text = (
        f"{icon} <b>Рестарт завершено</b>\n"
        f"🎯 Target: <code>{target.key}</code>\n"
        f"📦 Service: <code>{target.service}</code>\n"
        f"⚠️ Status: <code>{status}</code>"
    )
    
    await cb.message.answer(result_text, parse_mode="HTML")


@router.callback_query(F.data.startswith("quick_logs:"))
async def quick_logs_callback(cb: CallbackQuery, ctx: Context):
    """Показати останні 50 рядків логів."""
    target_key = cb.data.replace("quick_logs:", "")
    
    if target_key not in ctx.targets:
        await cb.answer("❌ Ціль не знайдена", show_alert=True)
        return
    
    target = ctx.targets[target_key]
    
    await cb.answer("⏳ Завантажую логи...", show_alert=True)
    
    logs = journalctl_lines(target.service, n=50, ctx=ctx)
    
    if not logs or logs.startswith("❌"):
        await cb.message.answer(
            f"📜 <b>Логи ({target.key})</b>\n\n❌ Логи недоступні",
            parse_mode="HTML"
        )
        return
    
    # Розбиваємо на chunks
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
        f"📜 <b>Логи ({target.key}) - останні 50 рядків</b>\n\n"
        f"<blockquote expandable>{safe_html(chunks[0], max_len=ctx.config.max_output_size)}</blockquote>",
        parse_mode="HTML",
    )
    
    for ch in chunks[1:]:
        await cb.message.answer(
            f"<blockquote expandable>{safe_html(ch, max_len=ctx.config.max_output_size)}</blockquote>",
            parse_mode="HTML",
        )
