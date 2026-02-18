"""Watchdog service for monitoring targets and sending alerts."""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Set

from aiogram import Bot

from app.context import Context
from app.services.journal import journalctl_lines
from app.services.systemd import systemctl_is_active


logger = logging.getLogger("admin_bot")

# Трекінг відправлених повідомлень для уникнення спаму
_last_alerts: Dict[str, datetime] = {}
_ALERT_COOLDOWN = timedelta(minutes=15)  # Не спамити однаковими alertами


def _should_send_alert(alert_key: str) -> bool:
    """Check if enough time passed since last alert of this type."""
    if alert_key not in _last_alerts:
        return True
    return datetime.now() - _last_alerts[alert_key] > _ALERT_COOLDOWN


def _mark_alert_sent(alert_key: str) -> None:
    """Mark alert as sent to prevent spam."""
    _last_alerts[alert_key] = datetime.now()


async def monitor_targets(bot: Bot, ctx: Context) -> None:
    """Continuously monitor all targets and send alerts on issues.

    Args:
        bot: Telegram bot instance
        ctx: Application context
    """
    logger.info("Watchdog started: monitoring %d targets", len(ctx.targets))

    while True:
        try:
            await asyncio.sleep(ctx.config.alert_interval)

            for target in ctx.targets.values():
                # Перевірка статусу сервісу
                status = systemctl_is_active(target.service, ctx=ctx).strip()
                if status != "active":
                    alert_key = f"service_down_{target.key}"
                    if _should_send_alert(alert_key):
                        await bot.send_message(
                            ctx.config.admin_id,
                            f"🚨 <b>ALERT: Service Down</b>\n\n"
                            f"🎯 Target: <code>{target.key}</code>\n"
                            f"📦 Service: <code>{target.service}</code>\n"
                            f"⚠️ Status: <code>{status}</code>\n"
                            f"⏰ Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>",
                            parse_mode="HTML",
                        )
                        _mark_alert_sent(alert_key)
                        logger.warning(f"Alert sent: {target.key} is {status}")

                # Перевірка критичних помилок в логах
                if ctx.config.alert_on_critical_errors:
                    recent_logs = journalctl_lines(target.service, n=50, ctx=ctx)
                    critical_pattern = re.compile(r"CRITICAL|FATAL", re.IGNORECASE)
                    critical_lines = [
                        ln for ln in recent_logs.splitlines() if critical_pattern.search(ln)
                    ]

                    if critical_lines:
                        # Беремо останню помилку
                        last_critical = critical_lines[-1][:200]  # Обрізаємо для ключа
                        alert_key = f"critical_{target.key}_{hash(last_critical)}"

                        if _should_send_alert(alert_key):
                            preview = "\n".join(critical_lines[-3:])  # Показуємо останні 3
                            await bot.send_message(
                                ctx.config.admin_id,
                                f"🔥 <b>ALERT: Critical Error</b>\n\n"
                                f"🎯 Target: <code>{target.key}</code>\n"
                                f"📦 Service: <code>{target.service}</code>\n"
                                f"📄 Errors found: <code>{len(critical_lines)}</code>\n\n"
                                f"<blockquote expandable>{preview[:1000]}</blockquote>",
                                parse_mode="HTML",
                            )
                            _mark_alert_sent(alert_key)
                            logger.warning(
                                f"Alert sent: {target.key} has {len(critical_lines)} critical errors"
                            )

        except asyncio.CancelledError:
            logger.info("Watchdog stopped")
            raise
        except Exception as e:
            logger.error(f"Watchdog error: {e}", exc_info=True)
            await asyncio.sleep(60)  # Пауза при помилці
