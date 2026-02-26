"""Сервіс моніторингу (watchdog) для спостереження за цілями та надсилання сповіщень."""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Set

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.context import Context
from app.services.journal import journalctl_lines
from app.services.systemd import systemctl_is_active


logger = logging.getLogger("admin_bot")

# Трекінг відправлених повідомлень для уникнення спаму
_last_alerts: Dict[str, datetime] = {}
_ALERT_COOLDOWN = timedelta(minutes=15)  # Не спамити однаковими alertами

# Помічені як "в роботі" алерти (не спамити доки не виправлять)
_acknowledged_alerts: Set[str] = set()


def _should_send_alert(alert_key: str) -> bool:
    """Перевірити чи можна відправити alert (не acknowledged і cooldown пройшов)."""
    # Якщо помічено як "в роботі" - не спамимо
    if alert_key in _acknowledged_alerts:
        return False
    
    if alert_key not in _last_alerts:
        return True
    return datetime.now() - _last_alerts[alert_key] > _ALERT_COOLDOWN


def _mark_alert_sent(alert_key: str) -> None:
    """Помітити alert як відправлений."""
    _last_alerts[alert_key] = datetime.now()


def acknowledge_alert(alert_key: str) -> None:
    """Помітити alert як 'в роботі' - більше не спамити доки не знято."""
    _acknowledged_alerts.add(alert_key)
    logger.info("Alert acknowledged: %s", alert_key)


def unacknowledge_alert(alert_key: str) -> None:
    """Зняти позначку 'в роботі' - дозволити alertи знову."""
    _acknowledged_alerts.discard(alert_key)
    logger.info("Alert unacknowledged: %s", alert_key)


async def monitor_targets(bot: Bot, ctx: Context) -> None:
    """Постійний моніторинг всіх цілей і відправка сповіщень.

    Args:
        bot: Екземпляр Telegram бота
        ctx: Контекст застосунку
    """
    logger.info("Моніторинг запущено: %d цілей", len(ctx.targets))

    while True:
        try:
            await asyncio.sleep(ctx.config.alert_interval)

            for target in ctx.targets.values():
                # Перевірка статусу сервісу
                status = systemctl_is_active(target.service, ctx=ctx).strip()
                if status != "active":
                    alert_key = f"service_down_{target.key}"
                    if _should_send_alert(alert_key):
                        kb = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="✅ Виправляємо...",
                                        callback_data=f"ack_alert:{alert_key}",
                                    ),
                                    InlineKeyboardButton(
                                        text="🔄 Перезапуск",
                                        callback_data=f"quick_restart:{target.key}",
                                    ),
                                ],
                            ]
                        )
                        await bot.send_message(
                            ctx.config.admin_id,
                            f"🚨 <b>СПОВІЩЕННЯ: Сервіс не працює</b>\n\n"
                            f"🎯 Ціль: <code>{target.key}</code>\n"
                            f"📦 Сервіс: <code>{target.service}</code>\n"
                            f"⚠️ Статус: <code>{status}</code>\n"
                            f"⏰ Час: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>",
                            parse_mode="HTML",
                            reply_markup=kb,
                        )
                        _mark_alert_sent(alert_key)
                        logger.warning("Alert sent: %s is %s", target.key, status)

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
                        alert_key = f"crit_{target.key}_{abs(hash(last_critical)) % 10**8}"

                        if _should_send_alert(alert_key):
                            preview = "\n".join(critical_lines[-3:])  # Показуємо останні 3
                            # Truncate alert_key for callback_data (Telegram 64-byte limit)
                            ack_data = f"ack_alert:{alert_key}"[:64]
                            kb = InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [
                                        InlineKeyboardButton(
                                            text="✅ Виправляємо...",
                                            callback_data=ack_data,
                                        ),
                                        InlineKeyboardButton(
                                            text="🔄 Перезапуск",
                                            callback_data=f"quick_restart:{target.key}",
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            text="📜 Повні логи",
                                            callback_data=f"quick_logs:{target.key}",
                                        ),
                                    ],
                                ]
                            )
                            await bot.send_message(
                                ctx.config.admin_id,
                                f"🔥 <b>СПОВІЩЕННЯ: Критична помилка</b>\n\n"
                                f"🎯 Ціль: <code>{target.key}</code>\n"
                                f"📦 Сервіс: <code>{target.service}</code>\n"
                                f"📄 Знайдено помилок: <code>{len(critical_lines)}</code>\n\n"
                                f"<blockquote expandable>{preview[:1000]}</blockquote>",
                                parse_mode="HTML",
                                reply_markup=kb,
                            )
                            _mark_alert_sent(alert_key)
                            logger.warning(
                                "Alert sent: %s has %d critical errors",
                                target.key,
                                len(critical_lines),
                            )

        except asyncio.CancelledError:
            logger.info("Моніторинг зупинено")
            raise
        except Exception as e:
            logger.error("Помилка моніторингу: %s", e, exc_info=True)
            await asyncio.sleep(60)  # Пауза при помилці
