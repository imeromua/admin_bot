import asyncio
import logging
import subprocess

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.context import Context


logger = logging.getLogger("admin_bot")
router = Router()


@router.callback_query(F.data == "restart_self")
async def restart_self_handler(cb: CallbackQuery, ctx: Context):
    await cb.answer("🔄 Перезапускаю Admin Bot...", show_alert=True)
    await cb.message.answer(
        f"🤖 <b>Ініційовано перезапуск {ctx.config.self_service_name}</b>\n"
        "Бот тимчасово недоступний. Зачекайте 10-15 секунд і натисніть /start.",
        parse_mode="HTML",
    )
    asyncio.create_task(_run_self_restart(ctx.config.self_service_name))


async def _run_self_restart(service_name: str):
    await asyncio.sleep(1)
    logger.warning("Ініційовано самоперезапуск для сервісу: %s", service_name)
    subprocess.run(["sudo", "systemctl", "restart", service_name])
