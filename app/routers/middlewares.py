import logging
from aiogram import Router


logger = logging.getLogger("admin_bot")


def admin_only(admin_id: int):
    async def _mw(handler, event, data):
        if hasattr(event, "from_user") and event.from_user and event.from_user.id != admin_id:
            logger.warning("Unauthorized access attempt from %s", event.from_user.id)
            return
        return await handler(event, data)

    return _mw
