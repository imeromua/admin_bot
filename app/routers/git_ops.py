from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.context import Context
from app.core.exec import safe_html, run_command
from app.services.git import git_pull


router = Router()


@router.message(F.text == "🚀 GIT PULL")
async def git_pull_menu(message: types.Message, ctx: Context):
    target = ctx.get_active_target(message.chat.id)

    buttons = [
        [InlineKeyboardButton(text=f"🎯 Pull target: {target.key}", callback_data="gitpull:target")],
        [InlineKeyboardButton(text=f"🤖 Pull admin_bot", callback_data="gitpull:self")],
    ]

    await message.answer(
        "🚀 <b>Оберіть що оновлювати</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "gitpull:target")
async def git_pull_target(cb: CallbackQuery, ctx: Context):
    target = ctx.get_active_target(cb.message.chat.id)
    msg = await cb.message.answer("⏳ <i>Git Pull (target)...</i>", parse_mode="HTML")

    pull_res, log1, updated = git_pull(target, ctx=ctx)
    icon = "✅" if (updated or "Already up to date" in pull_res) else "⚠️"

    text = (
        f"{icon} <b>GIT UPDATE</b> ({target.key})\n"
        f"🔖 {safe_html(log1, max_len=ctx.config.max_output_size)}\n"
        f"<blockquote expandable>{safe_html(pull_res, max_len=ctx.config.max_output_size)}</blockquote>"
    )
    await msg.edit_text(text, parse_mode="HTML")

    if updated:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=f"🔄 Restart {target.service}", callback_data="confirm_restart"),
                    InlineKeyboardButton(text=f"🤖 Restart {ctx.config.self_service_name}", callback_data="restart_self"),
                ]
            ]
        )
        await cb.message.answer("✅ Код оновився. Який сервіс перезапустити?", reply_markup=kb)

    await cb.answer()


@router.callback_query(F.data == "gitpull:self")
async def git_pull_self(cb: CallbackQuery, ctx: Context):
    msg = await cb.message.answer("⏳ <i>Git Pull (admin_bot)...</i>", parse_mode="HTML")

    pull_res = run_command(
        ["git", "pull"],
        cwd=ctx.repo_root,
        timeout=60,
        max_output_size=ctx.config.max_output_size,
    )
    log1 = run_command(
        ["git", "log", "-1", "--format=%h - %s (%cr) <%an>"],
        cwd=ctx.repo_root,
        timeout=30,
        max_output_size=ctx.config.max_output_size,
    )

    updated = ("Updating" in pull_res) or ("Fast-forward" in pull_res)
    icon = "✅" if (updated or "Already up to date" in pull_res) else "⚠️"

    repo_hint = f"\n🔗 Repo: <code>{safe_html(ctx.config.admin_repo, max_len=ctx.config.max_output_size)}</code>" if ctx.config.admin_repo else ""

    text = (
        f"{icon} <b>ADMIN BOT UPDATE</b>{repo_hint}\n"
        f"🔖 {safe_html(log1, max_len=ctx.config.max_output_size)}\n"
        f"<blockquote expandable>{safe_html(pull_res, max_len=ctx.config.max_output_size)}</blockquote>"
    )
    await msg.edit_text(text, parse_mode="HTML")

    if updated:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"🤖 Restart {ctx.config.self_service_name}", callback_data="restart_self")]]
        )
        await cb.message.answer("✅ Код admin_bot оновився. Перезапустити сервіс?", reply_markup=kb)

    await cb.answer()
