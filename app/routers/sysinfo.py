from aiogram import Router, F, types

from app.context import Context
from app.core.exec import safe_html
from app.services.system_info import collect_system_info


router = Router()


@router.message(F.text == "⚙️ Системна інфо")
async def system_info(message: types.Message, ctx: Context):
    target = ctx.get_active_target(message.chat.id)
    msg = await message.answer("⏳ <i>Збираю інформацію...</i>", parse_mode="HTML")

    info = collect_system_info(target, ctx=ctx)
    await msg.edit_text(info, parse_mode="HTML")
