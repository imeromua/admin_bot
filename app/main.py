import logging
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.context import Context
from app.core.config import load_config
from app.core.targets import load_targets
from app.routers.middlewares import admin_only
from app.storage.selection import SelectionStore

from app.routers import start, targets, logs, status, pip_ops, git_ops, restart, self_restart, self_update, env_ops, backup, sysinfo


logger = logging.getLogger("admin_bot")


def _build_context(repo_root: Path) -> Context:
    config = load_config()
    targets_map = load_targets(config.targets_str)
    selection = SelectionStore.load(repo_root / "state.json")

    return Context(config=config, targets=targets_map, selection=selection, repo_root=repo_root)


async def main_async():
    repo_root = Path(__file__).resolve().parents[1]
    ctx = _build_context(repo_root)

    bot = Bot(token=ctx.config.token)
    dp = Dispatcher()

    # middleware
    dp.message.middleware(admin_only(ctx.config.admin_id))
    dp.callback_query.middleware(admin_only(ctx.config.admin_id))

    # dependency injection via dp['ctx']
    dp["ctx"] = ctx

    # routers
    dp.include_router(start.router)
    dp.include_router(targets.router)
    dp.include_router(logs.router)
    dp.include_router(status.router)
    dp.include_router(pip_ops.router)
    dp.include_router(git_ops.router)
    dp.include_router(restart.router)
    dp.include_router(self_restart.router)
    dp.include_router(self_update.router)
    dp.include_router(env_ops.router)
    dp.include_router(backup.router)
    dp.include_router(sysinfo.router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Admin Bot started. Targets: %s", ",".join(ctx.targets.keys()))
        await dp.start_polling(bot, ctx=ctx)
    finally:
        await bot.session.close()


def run():
    import asyncio

    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
